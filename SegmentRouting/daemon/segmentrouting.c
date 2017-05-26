#include <sys/types.h>
#include <sys/socket.h>
#include <netinet/in.h>
#include <arpa/inet.h>
#include <sys/poll.h>
#include <string.h>
#include <stdlib.h>
#include <stdio.h>
#include <unistd.h>
#include <stdio.h>

#include <confd_lib.h>
#include <confd_cdb.h>

#include <confd_lib.h>
#include <confd_events.h>
#include <confd_maapi.h>
#include <netdb.h>
#include <stdint.h>

#define OK(E) assert((E) == CONFD_OK)

/* include generated file */
#include "segmentrouting.h"

/*** Some debug files ***/
char TOPOLOGY_CONFIG[] = "../debug/network.json";
char TOPOLOGY_CONFIG_TMP[] = "../debug/network.json.tmp";

char SR_CONFIG[] = "../debug/sr.json";
char SR_CONFIG_TMP[] = "../debug/sr.json.tmp";

char SR_OUT[] = "out/sr.json";
char TOPO_OUT[] = "out/network.json";

char ERROR_DELIMITER[50] = "\n\n*************************\n";
/** Global variable **/
int DEBUG = 0;
int MAXREQ = 1000;
int MAXREQSIZE = 1024;
int OVERLOAD = 0;

int Network_port = 50001;
int Controller_port = 60002;

//-----------------------------------------------------------
/**
 * Send config over socket to Application handler
 */
static int push_configuration(char *buffer, size_t buffer_len, int port) {

  int sockfd, portno, n;
  struct sockaddr_in serv_addr;
  struct hostent *server;

  // check buffer length
  if(strlen(buffer) != buffer_len) {
    printf(" ERROR : buffer_len\n" );
  }


  portno = port;

  /* Create a socket point */
  sockfd = socket(AF_INET, SOCK_STREAM, 0);

  if (sockfd < 0) {
     printf(ERROR_DELIMITER);
     perror("ERROR opening socket");
     printf(ERROR_DELIMITER);

    return sockfd;

  }

  server = gethostbyname("127.0.0.1");

  if (server == NULL) {
     fprintf(stderr,"ERROR, no such host\n");
     return -1;
  }

  bzero((char *) &serv_addr, sizeof(serv_addr));
  serv_addr.sin_family = AF_INET;
  bcopy((char *)server->h_addr, (char *)&serv_addr.sin_addr.s_addr, server->h_length);
  serv_addr.sin_port = htons(portno);

  /* Now connect to the server */
  if (connect(sockfd, (struct sockaddr*)&serv_addr, sizeof(serv_addr)) < 0) {
    printf(ERROR_DELIMITER);
     perror("ERROR connecting");
     printf(ERROR_DELIMITER);
     return -1;
  }
  /* Send message to the server */
  n = write(sockfd, buffer, strlen(buffer));

  if (n < 0) {
    printf(ERROR_DELIMITER);
     perror("ERROR writing to socket");
     printf(ERROR_DELIMITER);
     return n;

  }

  /* Now read server response */
  bzero(buffer, buffer_len);
  n = read(sockfd, buffer, 255);

  if (n < 0) {
    printf(ERROR_DELIMITER);
     perror("ERROR reading from socket");
     printf(ERROR_DELIMITER);
     return n;
  }

  printf("%s\n",buffer);

  close(sockfd);

  return 0;
}
/********************************************************************/
static int in_keys(char keys[MAXREQ][MAXREQSIZE], char *key) {
  int i;
  for(i=0; i< MAXREQ ; i++){
    if(strcmp(keys[i],key) == 0) {
      printf("table : %s\n",keys[i]);
      printf(" key : %s\n", key);
      return 1;
    }
  }
  return 0;
}
/********************************************************************/
static int read_conf_SR(struct sockaddr_in *addr, char keys[MAXREQ][MAXREQSIZE])
{
    FILE *fp, *fp_out_SR;

    int i, n;
    int rsock;

    // --------------------------------------------------------------------
    // SET UP the connection
    // --------------------------------------------------------------------
    if ((rsock = socket(PF_INET, SOCK_STREAM, 0)) < 0 )
        confd_fatal("Failed to open socket\n");

    if (cdb_connect(rsock, CDB_READ_SOCKET, (struct sockaddr*)addr,
                      sizeof (struct sockaddr_in)) < 0)
        return CONFD_ERR;
    if (cdb_start_session(rsock, CDB_RUNNING) != CONFD_OK)
        return CONFD_ERR;

    // --------------------------------------------------------------------
    // get name sapce from header file
    cdb_set_namespace(rsock, segmentrouting__ns);


    // --------------------------------------------------------------------
    //              GET CONFIGURATION CHANGES of Segment Routing
    // --------------------------------------------------------------------


    // --------------------------------------------------------------------
    if(DEBUG == 1) {
      // open the config file (create one if not exist yet)
      if ((fp = fopen(SR_CONFIG_TMP, "w")) == NULL) {
          cdb_close(rsock);
          return CONFD_ERR;
      }
    }



    // this will contain the config
    char buffer[MAXREQ*MAXREQSIZE];

    char tmpBuff[200];

    // GET ROUTERS LIST
    confd_value_t *values;


    sprintf(buffer, "{\"config\":");




    strcat(buffer, "{\"link\":[");
    n = cdb_num_instances(rsock, "/segment-routing/sr-requirement/requirement");


    // check  last requirement
    int l;
    int LAST_RUNNING = n;
    for(l=n-1; l>=0;l--){

      int tmp_status;
      cdb_get_enum_value(rsock, &tmp_status ,"/segment-routing/sr-requirement/requirement[%d]/state", l);
      if(tmp_status != segmentrouting_not_running) {
        LAST_RUNNING = l;
        break;
      }

    }

    for (i=0; i<=LAST_RUNNING; i++) {
        int status;
        cdb_get_enum_value(rsock, &status ,"/segment-routing/sr-requirement/requirement[%d]/state", i);

        if(status != segmentrouting_not_running) {
          unsigned char *buf2;
          int  buflen2;

          cdb_get_buf(rsock, &buf2, &buflen2,
                      "/segment-routing/sr-requirement/requirement[%d]/dest", i);


          unsigned char  *name;
          int name_len;
          char real_status[20];


          switch (status) {
            case segmentrouting_running:
              sprintf(real_status, "running");
              break;
            case segmentrouting_not_running:
              sprintf(real_status, "not-running");
              break;

            case segmentrouting_scheduled :
            sprintf(real_status, "scheduled");
            break;
          }

          cdb_get_buf(rsock, &name, &name_len,
                      "/segment-routing/sr-requirement/requirement[%d]/name", i);

          sprintf(tmpBuff, "{\"name\":\"%.*s\",", name_len, name);
          strcat(buffer, tmpBuff);

          char key[20];
          sprintf(key, "%.*s",name_len, name );
          if(OVERLOAD == 1 || in_keys(keys, key) == 1) {
            strcat(buffer, "\"change\":true,");
          } else {
            strcat(buffer, "\"change\":false,");
          }
          sprintf(tmpBuff, "\"dest\":\"%.*s\",", buflen2, buf2);
          strcat(buffer, tmpBuff);
          sprintf(tmpBuff, "\"status\":\"%s\",", real_status);
          strcat(buffer, tmpBuff);
          strcat(buffer, "\"scheduled\":{");

          int type;
          char real_type[20];
          cdb_get_enum_value(rsock, &type ,"/segment-routing/sr-requirement/requirement[%d]/schedule/Type", i);
          switch (type) {
            case segmentrouting_time:
              sprintf(real_type, "time");
              break;
            case segmentrouting_bandwidth:
              sprintf(real_type, "bandwidth");
              break;
            case segmentrouting_backup:
              sprintf(real_type, "backup");
              break;
          }

          sprintf(tmpBuff, "\"type\":\"%s\",", real_type);
          strcat(buffer, tmpBuff);

          if (status == segmentrouting_scheduled &&
              (type == segmentrouting_bandwidth || type == segmentrouting_backup )) {
            strcat(buffer, "\"link\":{");
            unsigned char *from,*to;
            int from_len, to_len;
            cdb_get_buf(rsock, &from, &from_len,
                        "/segment-routing/sr-requirement/requirement[%d]/schedule/link/from", i);


            cdb_get_buf(rsock, &to, &to_len,
                        "/segment-routing/sr-requirement/requirement[%d]/schedule/link/to", i);

            sprintf(tmpBuff, "\"from\":\"%.*s\",", from_len, from);
            strcat(buffer, tmpBuff);
            sprintf(tmpBuff, "\"to\":\"%.*s\",", to_len, to);
            strcat(buffer, tmpBuff);

            uint8_t bw_perc;
            cdb_get_u_int8(rsock, &bw_perc, "/segment-routing/sr-requirement/requirement[%d]/schedule/link/bw-percentage",i);
            sprintf(tmpBuff, "\"bw-perc\":\"%d\"},", bw_perc);
            strcat(buffer, tmpBuff);
          } else {
            strcat(buffer, "\"link\":{");
            strcat(buffer, "\"from\":\"\",");
            strcat(buffer, "\"to\":\"\",");
            strcat(buffer, "\"bw-perc\":100},");

          }



          unsigned char *start_hour,*end_hour;
          int start_hour_len, end_hour_len;
          cdb_get_buf(rsock, &start_hour, &start_hour_len,
                      "/segment-routing/sr-requirement/requirement[%d]/schedule/start-hour", i);
          //
          cdb_get_buf(rsock, &end_hour, &end_hour_len,
                      "/segment-routing/sr-requirement/requirement[%d]/schedule/end-hour", i);
          //
          sprintf(tmpBuff, "\"start-hour\":\"%.*s\",", start_hour_len, start_hour);
          strcat(buffer, tmpBuff);
          sprintf(tmpBuff, "\"end-hour\":\"%.*s\",", end_hour_len, end_hour);
          strcat(buffer, tmpBuff);
          strcat(buffer, "\"days\":[");

          int j,m;
          char pathString[100];
          if(status == segmentrouting_scheduled) {
            sprintf(pathString,"/segment-routing/sr-requirement/requirement[%d]/schedule/days", i );
            if(CONFD_ERR != cdb_get_list(rsock, &values, &m, pathString)) {
              for (j = 0; j < m; j++) {

                  if(j== m-1) {

                    sprintf(tmpBuff, "%d",  CONFD_GET_ENUM_VALUE(&values[j]));
                    strcat(buffer,tmpBuff);
                  } else {

                    sprintf(tmpBuff, "%d,", CONFD_GET_ENUM_VALUE(&values[j]));
                    strcat(buffer,tmpBuff);
                  }

                  confd_free_value(&values[j]);
              }
              free(values);
            }

          }
          strcat(buffer, "]},");

          strcat(buffer, "\"requirement\":[");

          sprintf(pathString,"/segment-routing/sr-requirement/requirement[%d]/Path", i );
          if(CONFD_ERR != cdb_get_list(rsock, &values, &m, pathString)) {
            for (j = 0; j < m; j++) {

                if(j== m-1) {

                  sprintf(tmpBuff, "\"%s\"",  CONFD_GET_BUFPTR(&values[j]));
                  strcat(buffer,tmpBuff);
                } else {

                  sprintf(tmpBuff, "\"%s\",", CONFD_GET_BUFPTR(&values[j]));
                  strcat(buffer,tmpBuff);
                }

                confd_free_value(&values[j]);
            }
            free(values);
          }


          if(i == LAST_RUNNING) {

            strcat(buffer, "]}");
          } else {

            strcat(buffer, "]},");
          }
        }



    }


    strcat(buffer, "]}");


    strcat(buffer, "}");

    // free(values);
    // --------------------------------------------------------------------
    //              FINISH CONFIG
    // --------------------------------------------------------------------

      if(DEBUG == 1) {
        fprintf(fp, "%s", buffer );
        fclose(fp);
        // --------------------------------------------------------------------
        //              RENAME CONFIG FILE
        rename(SR_CONFIG_TMP, SR_CONFIG);

      }

      if ((fp_out_SR = fopen(SR_OUT, "w")) == NULL) {
          return CONFD_ERR;
      }

      fprintf(fp_out_SR, buffer);
      fclose(fp_out_SR);


    push_configuration(buffer,strlen(buffer), Controller_port);


    return cdb_close(rsock);
}

/********************************************************************/
static int read_conf_Network(struct sockaddr_in *addr)
{
    FILE *fp, *fp_out_topo;
    // struct confd_duration dur;
    int i, n;
    int rsock;

    // --------------------------------------------------------------------
    // SET UP the connection
    // --------------------------------------------------------------------
    if ((rsock = socket(PF_INET, SOCK_STREAM, 0)) < 0 )
        confd_fatal("Failed to open socket\n");

    if (cdb_connect(rsock, CDB_READ_SOCKET, (struct sockaddr*)addr,
                      sizeof (struct sockaddr_in)) < 0)
        return CONFD_ERR;
    if (cdb_start_session(rsock, CDB_RUNNING) != CONFD_OK)
        return CONFD_ERR;

    // --------------------------------------------------------------------
    // get name sapce from header file
    cdb_set_namespace(rsock, segmentrouting__ns);

    if(DEBUG == 1) {
      // --------------------------------------------------------------------
      // open the config file (create one if not exist yet)
      if ((fp = fopen(TOPOLOGY_CONFIG_TMP, "w")) == NULL) {
          return CONFD_ERR;
      }

    }


    // this will contain the config
    char buffer[MAXREQ*MAXREQSIZE];

    char tmpBuff[200];

    sprintf(buffer, "{\"link\":[");
    n = cdb_num_instances(rsock, "/segment-routing/network/link");
    for(i=0;i<n;i++){
      unsigned char *src_name;
      int src_name_len;
      cdb_get_buf(rsock, &src_name, &src_name_len,
                  "/segment-routing/network/link[%d]/src/name", i);
      //

      unsigned char *dest_name;
      int dest_name_len;
      cdb_get_buf(rsock, &dest_name, &dest_name_len,
                  "/segment-routing/network/link[%d]/dest/name", i);
      //

      unsigned char *link_name;
      int link_name_len;
      cdb_get_buf(rsock, &link_name, &link_name_len,
                  "/segment-routing/network/link[%d]/name", i);
      //

      unsigned char *src_ip;
      int src_ip_len;
      cdb_get_buf(rsock, &src_ip, &src_ip_len,
                  "/segment-routing/network/link[%d]/src/ip", i);
      //
      unsigned char *dest_ip;
      int dest_ip_len;
      cdb_get_buf(rsock, &dest_ip, &dest_ip_len,
                  "/segment-routing/network/link[%d]/dest/ip", i);
      //

      int bw, cost, delay;
      cdb_get_int32(rsock, &bw, "/segment-routing/network/link[%d]/bw",i);
      cdb_get_int32(rsock, &cost, "/segment-routing/network/link[%d]/cost",i);
      cdb_get_int32(rsock, &delay, "/segment-routing/network/link[%d]/delay",i);

      uint16_t src_cost, dest_cost;
      cdb_get_u_int16(rsock, &src_cost, "/segment-routing/network/link[%d]/src/cost", i);
      cdb_get_u_int16(rsock, &dest_cost, "/segment-routing/network/link[%d]/dest/cost", i);
      int is_bidirectional;
      cdb_get_bool(rsock, &is_bidirectional, "/segment-routing/network/link[%d]/bidirectional", i);

      strcat(buffer,"{\"src\":{");
      sprintf(tmpBuff,"\"name\":\"%.*s\",",
        src_name_len,src_name);
      strcat(buffer,tmpBuff);
      sprintf(tmpBuff,"\"cost\" :%d,", src_cost);
      strcat(buffer,tmpBuff);
      sprintf(tmpBuff,"\"ip\":\"%.*s\"},",src_ip_len, src_ip);
      strcat(buffer,tmpBuff);

      strcat(buffer,"\"dest\":{");
      sprintf(tmpBuff,"\"name\" :\"%.*s\",",
        dest_name_len,dest_name);
      strcat(buffer,tmpBuff);
      sprintf(tmpBuff,"\"cost\" :%d,", dest_cost);
      strcat(buffer,tmpBuff);
      sprintf(tmpBuff,"\"ip\":\"%.*s\"},",dest_ip_len, dest_ip);
      strcat(buffer,tmpBuff);

      sprintf(tmpBuff, "\"name\":\"%.*s\",",
      link_name_len, link_name);
      strcat(buffer,tmpBuff);
      if(is_bidirectional == 1) {
      strcat(buffer,"\"bidirectional\" : true,");
      }else {
        strcat(buffer,"\"bidirectional\" : false,");
      }
      sprintf(tmpBuff,"\"cost\":%d,",cost);
      strcat(buffer,tmpBuff);
      sprintf(tmpBuff,"\"bw\" :%d,",bw);
      strcat(buffer,tmpBuff);
      sprintf(tmpBuff,"\"delay\":%d}",delay);
      strcat(buffer,tmpBuff);

      if(i != n-1) {
        strcat(buffer,",");
      }
    }
    strcat(buffer,"],");

    strcat(buffer,"\"routers\":[");
    n = cdb_num_instances(rsock, "/segment-routing/network/router");
    for(i=0;i<n;i++){
      unsigned char *r_name;
      int r_name_len;
      cdb_get_buf(rsock, &r_name, &r_name_len,
                  "/segment-routing/network/router[%d]/name", i);
      //

      // Ignore if it is a '*' empty router
      char star[20];
      if(r_name_len < 20) {
        sprintf(star, "%.*s", r_name_len, r_name);
      }

      if (strcmp(star,"*")!=0 ) {

        unsigned char *loopback_addr;
        int loopback_addr_len;
        cdb_get_buf(rsock, &loopback_addr, &loopback_addr_len,
                    "/segment-routing/network/router[%d]/loopback-addr", i);
        //
        int r_ospf_enable;
        cdb_get_bool(rsock, &r_ospf_enable, "/segment-routing/network/router[%d]/ospf/enable", i);

        struct in_addr router_id;
        cdb_get_ipv4(rsock, &router_id, "/segment-routing/network/router[%d]/ospf/router-id", i);

        struct in_addr r_ospf_area;
        cdb_get_ipv4(rsock, &r_ospf_area, "/segment-routing/network/router[%d]/ospf/area", i);

        uint16_t src_hello_interval, src_dead_interval;
        cdb_get_u_int16(rsock, &src_hello_interval, "/segment-routing/network/router[%d]/ospf/hello-interval", i);
        cdb_get_u_int16(rsock, &src_dead_interval, "/segment-routing/network/router[%d]/ospf/dead-interval", i);

        // get lsa config
        uint8_t intf_delay, intf_initial_holdtime, intf_max_holdtime;
        uint16_t  intf_min_ls_arrival, intf_min_ls_interaval;
        cdb_get_u_int8(rsock, &intf_delay, "/segment-routing/network/router[%d]/ospf/throttle/delay",i);
        cdb_get_u_int8(rsock, &intf_initial_holdtime, "/segment-routing/network/router[%d]/ospf/throttle/initial_holdtime",i);
        cdb_get_u_int8(rsock, &intf_max_holdtime, "/segment-routing/network/router[%d]/ospf/throttle/max_holdtime",i);
        cdb_get_u_int16(rsock, &intf_min_ls_arrival, "/segment-routing/network/router[%d]/ospf/lsa/min_ls_arrival",i);
        cdb_get_u_int16(rsock, &intf_min_ls_interaval, "/segment-routing/network/router[%d]/ospf/lsa/min_ls_interval",i);
        struct in_addr intf_area;
        cdb_get_ipv4(rsock, &intf_area, "/segment-routing/network/router[%d]/ospf/area",i);


        sprintf(tmpBuff,"{\"name\":\"%.*s\",",
          r_name_len,r_name);
        strcat(buffer,tmpBuff);
        strcat(buffer,"\"ospf6\":{");
        if(r_ospf_enable == 1) {
          strcat(buffer,"\"enable\":true,");
        } else if(r_ospf_enable == 0) {
          strcat(buffer,"\"enable\":false,");
        }
        sprintf(tmpBuff, "\"area\":\"%s\",", inet_ntoa(r_ospf_area));
        strcat(buffer,tmpBuff);
        strcat(buffer, "\"throttle\":{");
        sprintf(tmpBuff, "\"delay\":%d,", intf_delay);
        strcat(buffer,tmpBuff);
        sprintf(tmpBuff, "\"initial_holdtime\":%d,", intf_initial_holdtime);
        strcat(buffer,tmpBuff);
        sprintf(tmpBuff, "\"max_holdtime\":%d},", intf_max_holdtime);
        strcat(buffer,tmpBuff);

        strcat(buffer, "\"lsa\":{");
        sprintf(tmpBuff, "\"min_ls_arrival\":%d,", intf_min_ls_arrival);
        strcat(buffer,tmpBuff);
        sprintf(tmpBuff, "\"min_ls_interval\":%d},", intf_min_ls_interaval);
        strcat(buffer,tmpBuff);
        sprintf(tmpBuff, "\"hello-interval\":%d,", src_hello_interval);
        strcat(buffer,tmpBuff);
        sprintf(tmpBuff, "\"dead-interval\":%d,", src_dead_interval);
        strcat(buffer,tmpBuff);
        sprintf(tmpBuff, "\"router-id\":\"%s\"},", inet_ntoa(router_id));
        strcat(buffer,tmpBuff);
        sprintf(tmpBuff,"\"loopback-addr\":\"%.*s\"}", loopback_addr_len, loopback_addr);
        strcat(buffer,tmpBuff);
        if(i != n-1) {
          strcat(buffer,",");
        }
      }

    }

    strcat(buffer,"],");

    strcat(buffer,"\"ospf-links\":[");
    n = cdb_num_instances(rsock, "/segment-routing/network/ospf-link-config");
    for(i=0;i<n;i++){
      unsigned char *link_name;
      int link_name_len;
      cdb_get_buf(rsock, &link_name, &link_name_len,
                  "/segment-routing/network/ospf-link-config[%d]/link-name", i);
      //

      uint16_t src_hello_interval, src_dead_interval;
      cdb_get_u_int16(rsock, &src_hello_interval, "/segment-routing/network/ospf-link-config[%d]/src/hello-interval", i);
      cdb_get_u_int16(rsock, &src_dead_interval, "/segment-routing/network/ospf-link-config[%d]/src/dead-interval", i);

      // get lsa config
      uint8_t intf_delay, intf_initial_holdtime, intf_max_holdtime;
      uint16_t  intf_min_ls_arrival, intf_min_ls_interaval;
      cdb_get_u_int8(rsock, &intf_delay, "/segment-routing/network/ospf-link-config[%d]/src/throttle/delay",i);
      cdb_get_u_int8(rsock, &intf_initial_holdtime, "/segment-routing/network/ospf-link-config[%d]/src/throttle/initial_holdtime",i);
      cdb_get_u_int8(rsock, &intf_max_holdtime, "/segment-routing/network/ospf-link-config[%d]/src/throttle/max_holdtime",i);
      cdb_get_u_int16(rsock, &intf_min_ls_arrival, "/segment-routing/network/ospf-link-config[%d]/src/lsa/min_ls_arrival",i);
      cdb_get_u_int16(rsock, &intf_min_ls_interaval, "/segment-routing/network/ospf-link-config[%d]/src/lsa/min_ls_interval",i);
      struct in_addr intf_area;
      cdb_get_ipv4(rsock, &intf_area, "/segment-routing/network/ospf-link-config[%d]/src/area",i);

      sprintf(tmpBuff,"{\"name\":\"%.*s\",",
        link_name_len,link_name);
      strcat(buffer,tmpBuff);

      strcat(buffer,"\"src\":{");
      strcat(buffer,"\"ospf\":{");
      sprintf(tmpBuff, "\"hello-interval\":%d,\"dead-interval\":%d,\n",
                src_hello_interval, src_dead_interval);
      strcat(buffer,tmpBuff);

      sprintf(tmpBuff, "\"area\":\"%s\",", inet_ntoa(intf_area));
      strcat(buffer,tmpBuff);

      strcat(buffer, "\"throttle\":{");
      sprintf(tmpBuff, "\"delay\":%d,", intf_delay);
      strcat(buffer,tmpBuff);
      sprintf(tmpBuff, "\"initial_holdtime\":%d,", intf_initial_holdtime);
      strcat(buffer,tmpBuff);
      sprintf(tmpBuff, "\"max_holdtime\":%d},", intf_max_holdtime);
      strcat(buffer,tmpBuff);

      strcat(buffer, "\"lsa\":{");
      sprintf(tmpBuff, "\"min_ls_arrival\":%d,", intf_min_ls_arrival);
      strcat(buffer,tmpBuff);
      sprintf(tmpBuff, "\"min_ls_interval\":%d}}", intf_min_ls_interaval);
      strcat(buffer,tmpBuff);
      strcat(buffer,"},"); // src


      uint16_t dest_hello_interval, dest_dead_interval;
      cdb_get_u_int16(rsock, &dest_hello_interval, "/segment-routing/network/ospf-link-config[%d]/dest/hello-interval", i);
      cdb_get_u_int16(rsock, &dest_dead_interval, "/segment-routing/network/ospf-link-config[%d]/dest/dead-interval", i);

      // get lsa config
      uint8_t intf_delay_dest, intf_initial_holdtime_dest, intf_max_holdtime_dest;
      uint16_t  intf_min_ls_arrival_dest, intf_min_ls_interaval_dest;
      cdb_get_u_int8(rsock, &intf_delay_dest, "/segment-routing/network/ospf-link-config[%d]/dest/throttle/delay",i);
      cdb_get_u_int8(rsock, &intf_initial_holdtime_dest, "/segment-routing/network/ospf-link-config[%d]/dest/throttle/initial_holdtime",i);
      cdb_get_u_int8(rsock, &intf_max_holdtime_dest, "/segment-routing/network/ospf-link-config[%d]/dest/throttle/max_holdtime",i);
      cdb_get_u_int16(rsock, &intf_min_ls_arrival_dest, "/segment-routing/network/ospf-link-config[%d]/dest/lsa/min_ls_arrival",i);
      cdb_get_u_int16(rsock, &intf_min_ls_interaval_dest, "/segment-routing/network/ospf-link-config[%d]/dest/lsa/min_ls_interval",i);
      struct in_addr intf_area_dest;
      cdb_get_ipv4(rsock, &intf_area_dest, "/segment-routing/network/ospf-link-config[%d]/dest/area",i);



      strcat(buffer,"\"dest\":{");
      strcat(buffer,"\"ospf\":{");
      sprintf(tmpBuff, "\"hello-interval\":%d,\"dead-interval\":%d,\n",
                dest_hello_interval, dest_dead_interval);
      strcat(buffer,tmpBuff);

      sprintf(tmpBuff, "\"area\":\"%s\",", inet_ntoa(intf_area_dest));
      strcat(buffer,tmpBuff);

      strcat(buffer, "\"throttle\":{");
      sprintf(tmpBuff, "\"delay\":%d,", intf_delay_dest);
      strcat(buffer,tmpBuff);
      sprintf(tmpBuff, "\"initial_holdtime\":%d,", intf_initial_holdtime_dest);
      strcat(buffer,tmpBuff);
      sprintf(tmpBuff, "\"max_holdtime\":%d},", intf_max_holdtime_dest);
      strcat(buffer,tmpBuff);

      strcat(buffer, "\"lsa\":{");
      sprintf(tmpBuff, "\"min_ls_arrival\":%d,", intf_min_ls_arrival_dest);
      strcat(buffer,tmpBuff);
      sprintf(tmpBuff, "\"min_ls_interval\":%d}}", intf_min_ls_interaval_dest);
      strcat(buffer,tmpBuff);
      strcat(buffer,"}"); // dest
      strcat(buffer,"}");// name


      if(i != n-1) {
        strcat(buffer,",");
      }
    }
    strcat(buffer,"],"); // ospf-links


    unsigned char *c_name;
    int c_name_len;
    cdb_get_buf(rsock, &c_name, &c_name_len,
                "/segment-routing/network/main-controller");
    //
    sprintf(tmpBuff,"\"controller\":\"%.*s\",",
      c_name_len,c_name);
    strcat(buffer,tmpBuff);


    strcat(buffer,"\"destinations\":[");
    n = cdb_num_instances(rsock, "/segment-routing/network/destinations");
    for(i=0;i<n;i++){
      unsigned char *d_name;
      int d_name_len;
      cdb_get_buf(rsock, &d_name, &d_name_len,
                  "/segment-routing/network/destinations[%d]/name", i);
      //


      sprintf(tmpBuff,"{\"name\":\"%.*s\"}",
        d_name_len,d_name);
      strcat(buffer,tmpBuff);

      if(i != n-1) {
        strcat(buffer,",");
      }
    }

    strcat(buffer,"]");


    strcat(buffer,"}");
    if(DEBUG == 1) {
      // --------------------------------------------------------------------
      //              FINISH CONFIG
      // --------------------------------------------------------------------
      fprintf(fp, buffer);
      fclose(fp);

      // --------------------------------------------------------------------
      //              RENAME CONFIG FILE

      rename(TOPOLOGY_CONFIG_TMP, TOPOLOGY_CONFIG);
    }

    if ((fp_out_topo = fopen(TOPO_OUT, "w")) == NULL) {
        return CONFD_ERR;
    }

    fprintf(fp_out_topo, buffer);
    fclose(fp_out_topo);



    push_configuration(buffer, strlen(buffer), Network_port);


    return cdb_close(rsock);
}

/********************************************************************/
static void print_modifications(confd_tag_value_t *val, int nvals,
                                struct confd_cs_node *start_node,
                                int start_indent,
                                struct sockaddr_in *addr,
                                char keys[MAXREQ][MAXREQSIZE])
{
    int i, indent = start_indent;
    struct confd_cs_node root, *pnode = start_node, *node;
    char tmpbuf[BUFSIZ];
    char *tmp;

    int rsock;

    // --------------------------------------------------------------------
    // SET UP the connection
    // --------------------------------------------------------------------
    if ((rsock = socket(PF_INET, SOCK_STREAM, 0)) < 0 )
        confd_fatal("Failed to open socket\n");

    if (cdb_connect(rsock, CDB_READ_SOCKET, (struct sockaddr*)addr,
                      sizeof (struct sockaddr_in)) < 0)
        return ;
    if (cdb_start_session(rsock, CDB_RUNNING) != CONFD_OK)
        return ;

    // --------------------------------------------------------------------
    // get name sapce from header file
    cdb_set_namespace(rsock, segmentrouting__ns);
    int key_index = 0;
    for (i=0; i<nvals; i++) {
        if (indent == start_indent && start_node == NULL) {
            node = confd_find_cs_root(CONFD_GET_TAG_NS(&val[i]));
            root.children = node;
            pnode = &root;
        }
        switch (CONFD_GET_TAG_VALUE(&val[i])->type) {
        case C_XMLBEGIN:
            tmp = "begin";
            if (pnode != NULL)
                pnode = confd_find_cs_node_child(pnode, val[i].tag);
            break;
        case C_XMLBEGINDEL:
            tmp = "begin-deleted";
            if (pnode != NULL)
                pnode = confd_find_cs_node_child(pnode, val[i].tag);
            break;
        case C_XMLEND:
            tmp = "end";
            if (pnode != NULL)
                pnode = pnode->parent;
            indent -= 2;
            break;
        case C_XMLTAG:
            tmp = "created";
            break;
        case C_NOEXISTS:
            tmp = "deleted";
            break;
        default:
            if (pnode == NULL ||
                (node = confd_find_cs_node_child(pnode, val[i].tag)) == NULL ||
                confd_val2str(node->info.type, CONFD_GET_TAG_VALUE(&val[i]),
                              tmpbuf, sizeof(tmpbuf)) == CONFD_ERR) {
                confd_pp_value(tmpbuf, sizeof(tmpbuf),
                               CONFD_GET_TAG_VALUE(&val[i]));
            }
            tmp = tmpbuf;
            char Path[BUFSIZ];
            sprintf(Path, "/segment-routing/sr-requirement/requirement{%s}/state", tmp);

            int status = cdb_exists(rsock, Path);
            if(status != CONFD_ERR && status == 1) {
              printf("\n>>>> key : %s\n", tmp);
              char KEY[MAXREQSIZE];
              sprintf(KEY,"%s", tmp);
              strcpy( keys[key_index], KEY);
              if (key_index +2> MAXREQ) {
                OVERLOAD = 1;
              } else {
                key_index++;
              }
            }

        }
        printf("%*s%s %s\n", indent, "",
               confd_hash2str(CONFD_GET_TAG_TAG(&val[i])), tmp);


        switch (CONFD_GET_TAG_VALUE(&val[i])->type) {
        case C_XMLBEGIN:
        case C_XMLBEGINDEL:
            indent += 2;
            break;
        default:
            break;
        }
    }
    cdb_close(rsock);
}


/********************************************************************/

int main(int argc, char **argv)
{
    struct sockaddr_in addr;
    int subsock;
    int status;
    int spoint;

    addr.sin_addr.s_addr = inet_addr("127.0.0.1");
    addr.sin_family = AF_INET;
    addr.sin_port = htons(CONFD_PORT);

    confd_init(argv[0], stderr, CONFD_TRACE);


    /*
     * Get Debug flag
     */
    if (argc == 4  ){
      if (argv[3][0]=='1') {
        printf("************ DEBUG : 1\n"  );
        DEBUG = 1;
      }
      MAXREQ = atoi(argv[1]);
      MAXREQSIZE = atoi(argv[2]);

      printf("**** MAXREQ: %d\n", MAXREQ);
      printf("**** MAXREQSIZE: %d\n", MAXREQSIZE);
    } else if (argc ==3) {
      MAXREQ = atoi(argv[1]);
      MAXREQSIZE = atoi(argv[2]);

      printf("**** MAXREQ: %d\n", MAXREQ);
      printf("**** MAXREQSIZE: %d\n", MAXREQSIZE);
    }

    /*
     * Setup subscriptions
     */
    if ((subsock = socket(PF_INET, SOCK_STREAM, 0)) < 0 )
        confd_fatal("Failed to open socket\n");

    if (cdb_connect(subsock, CDB_SUBSCRIPTION_SOCKET, (struct sockaddr*)&addr,
                      sizeof (struct sockaddr_in)) < 0)
        confd_fatal("Failed to cdb_connect() to confd \n");

      // Subscription to /mininet
    if ((status = cdb_subscribe(subsock, 3, segmentrouting__ns, &spoint, "/segment-routing"))
        != CONFD_OK) {
        fprintf(stderr, "Terminate: subscribe %d\n", status);
        exit(0);
    }
    if (cdb_subscribe_done(subsock) != CONFD_OK)
        confd_fatal("cdb_subscribe_done() failed");
    printf("Subscription point = %d\n", spoint);



    char keys[MAXREQ][MAXREQSIZE];

    while (1) {

        static int poll_fail_counter=0;
        struct pollfd set[1];

        set[0].fd = subsock;
        set[0].events = POLLIN;
        set[0].revents = 0;

        if (poll(&set[0], 1, -1) < 0) {
            perror("Poll failed:");
            if(++poll_fail_counter < 10)
                continue;
            fprintf(stderr, "Too many poll failures, terminating\n");
            exit(1);
        }

        poll_fail_counter = 0;
        if (set[0].revents & POLLIN) {


            int sub_points[1];
            int reslen;

            if ((status = cdb_read_subscription_socket(subsock,
                                                       &sub_points[0],
                                                       &reslen)) != CONFD_OK) {
                fprintf(stderr, "terminate sub_read: %d\n", status);
                exit(1);
            }
            if (reslen > 0) {


              confd_tag_value_t *values;
              int nvalues, i;
              int flags = CDB_GET_MODS_INCLUDE_LISTS;



              if (cdb_get_modifications(subsock, sub_points[0], flags, &values, &nvalues,
                                        "/segment-routing/sr-requirement") == CONFD_OK) {

                  printf("Modifications to subscription committed:\n");
                  print_modifications(values, nvalues, NULL, 0, &addr,keys);
                  printf("******** \n >> SR  : %d\n", nvalues);


                  if(nvalues != 0) {

                    //------------------------------------------------
                      if ((status = read_conf_SR(&addr, keys)) != CONFD_OK) {
                          fprintf(stderr, "Terminate: read_conf %d\n", status);
                          exit(1);
                      }

                  }

                  for (i = 0; i < nvalues; i++){
                    confd_free_value(CONFD_GET_TAG_VALUE(&values[i]));
                  }
                  free(values);

                  for(i=0; i< MAXREQ; i++) {
                    // reseting all keys
                    strcpy( keys[i], "");
                  }
                  OVERLOAD = 0;
              }

              if (cdb_get_modifications(subsock, sub_points[0], flags, &values, &nvalues,
                                        "/segment-routing/network") == CONFD_OK) {


                  printf("******** \n >> network  : %d\n", nvalues);

                  if(nvalues != 0) {
                    //------------------------------------------------
                      if ((status = read_conf_Network(&addr)) != CONFD_OK) {
                          fprintf(stderr, "Terminate: read_conf %d\n", status);
                          exit(1);
                      }
                  }

                  for (i = 0; i < nvalues; i++)
                      confd_free_value(CONFD_GET_TAG_VALUE(&values[i]));
                  free(values);
              }

            }


            fprintf(stderr, " \n\n Finish reading new config, listening \n");




            /* this is the place to HUP the daemon */

            if ((status = cdb_sync_subscription_socket(subsock,
                                                       CDB_DONE_PRIORITY))
                != CONFD_OK) {
                fprintf(stderr, "failed to sync subscription: %d\n", status);
                exit(1);
            }


        }
    }
}

/********************************************************************/
