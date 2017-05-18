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
#include "fibbing.h"
/** debug files **/
char TOPOLOGY_CONFIG[] = "../configfiles/mininet.conf";
char TOPOLOGY_CONFIG_TMP[] = "../configfiles/mininet.conf.tmp";

char FIBBING_CONFIG[] = "../configfiles/fibbing.conf";
char FIBBING_CONFIG_TMP[] = "../configfiles/fibbing.conf.tmp";
char ERROR_DELIMITER[50] = "\n\n*************************\n";

char Fib_OUT[] = "out/req.json";
char TOPO_OUT[] = "out/network.json";

/*** some Global variables ***/
int DEBUG = 0;
int MAXREQ = 500;
int MAXREQSIZE = 20;
int OVERLOAD = 0;
int Network_port = 50001;
int Controller_port = 60002;

//-----------------------------------------------------------
/***
 *  send config to Application handler
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
static int read_conf_Fibbing(struct sockaddr_in *addr,char keys[MAXREQ][MAXREQSIZE] )
{
    FILE *fp;
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
    cdb_set_namespace(rsock, fibbing__ns);


    // --------------------------------------------------------------------
    //              GET CONFIGURATION CHANGES of fibbing
    // --------------------------------------------------------------------


    // --------------------------------------------------------------------
    if(DEBUG == 1) {
      // open the config file (create one if not exist yet)
      if ((fp = fopen(FIBBING_CONFIG_TMP, "w")) == NULL) {
          cdb_close(rsock);
          return CONFD_ERR;
      }
    }


    // this will contain the config
    char buffer[MAXREQ*MAXREQSIZE];

    char tmpBuff[200];

    // GET ROUTERS LIST
    confd_value_t *values;


    sprintf(buffer, "{\"config\" : ");


    strcat(buffer, "{\"link\" : [");
    n = cdb_num_instances(rsock, "/fibbing/fibbing-requirement/requirement");


    // check  last requirement
    int l;
    int LAST_RUNNING = n;
    for(l=n-1; l>=0;l--){

      int tmp_status;
      cdb_get_enum_value(rsock, &tmp_status ,"/fibbing/fibbing-requirement/requirement[%d]/state", l);
      if(tmp_status != fibbing_not_running) {
        LAST_RUNNING = l;
        break;
      }

    }

    for (i=0; i<=LAST_RUNNING; i++) {

        int status;
        cdb_get_enum_value(rsock, &status ,"/fibbing/fibbing-requirement/requirement[%d]/state", i);

        if(status != fibbing_not_running) {
          unsigned char *buf2;
          int buflen2;


          cdb_get_buf(rsock, &buf2, &buflen2,
                      "/fibbing/fibbing-requirement/requirement[%d]/dest", i);


          unsigned char  *name;
          int name_len;

          char real_status[20];


          switch (status) {
            case fibbing_running:
              sprintf(real_status, "running");
              break;
            case fibbing_not_running:
              sprintf(real_status, "not-running");
              break;

            case fibbing_scheduled :
            sprintf(real_status, "scheduled");
            break;
          }

          cdb_get_buf(rsock, &name, &name_len,
                      "/fibbing/fibbing-requirement/requirement[%d]/name", i);

          sprintf(tmpBuff, "{ \"name\" : \"%.*s\",", name_len, name);
          strcat(buffer, tmpBuff);
          char key[20];
          sprintf(key, "%.*s",name_len, name );
          if(OVERLOAD==1 || in_keys(keys, key) == 1) {
            strcat(buffer, "\"change\" : true,");
          } else {
            strcat(buffer, "\"change\" : false,");
          }
          sprintf(tmpBuff, "\"dest\" : \"%.*s\",", buflen2, buf2);
          strcat(buffer, tmpBuff);
          sprintf(tmpBuff, "\"status\" : \"%s\",", real_status);
          strcat(buffer, tmpBuff);
          strcat(buffer, "\"scheduled\" :{ ");

          int type;
          char real_type[20];
          cdb_get_enum_value(rsock, &type ,"/fibbing/fibbing-requirement/requirement[%d]/schedule/Type", i);
          switch (type) {
            case fibbing_time:
              sprintf(real_type, "time");
              break;
            case fibbing_bandwidth:
              sprintf(real_type, "bandwidth");
              break;
            case fibbing_backup:
              sprintf(real_type, "backup");
              break;
          }

          sprintf(tmpBuff, "\"type\" : \"%s\",", real_type);
          strcat(buffer, tmpBuff);

          if (status == fibbing_scheduled &&
              (type == fibbing_bandwidth || type == fibbing_backup )) {
            strcat(buffer, "\"link\" : {");
            unsigned char *from,*to;
            int from_len, to_len;
            cdb_get_buf(rsock, &from, &from_len,
                        "/fibbing/fibbing-requirement/requirement[%d]/schedule/link/from", i);


            cdb_get_buf(rsock, &to, &to_len,
                        "/fibbing/fibbing-requirement/requirement[%d]/schedule/link/to", i);

            sprintf(tmpBuff, "\"from\" : \"%.*s\",", from_len, from);
            strcat(buffer, tmpBuff);
            sprintf(tmpBuff, "\"to\" : \"%.*s\",", to_len, to);
            strcat(buffer, tmpBuff);

            uint8_t bw_perc;
            cdb_get_u_int8(rsock, &bw_perc, "/fibbing/fibbing-requirement/requirement[%d]/schedule/link/bw-percentage",i);
            sprintf(tmpBuff, "\"bw-perc\" : %d},", bw_perc);
            strcat(buffer, tmpBuff);
          } else {
            strcat(buffer, "\"link\" : {");
            strcat(buffer, "\"from\" : \"\",");
            strcat(buffer, "\"to\" : \"\",");
            strcat(buffer, "\"bw-perc\" : \"100\"},");

          }



          unsigned char *start_hour,*end_hour;
          int start_hour_len, end_hour_len;
          cdb_get_buf(rsock, &start_hour, &start_hour_len,
                      "/fibbing/fibbing-requirement/requirement[%d]/schedule/start-hour", i);
          //
          cdb_get_buf(rsock, &end_hour, &end_hour_len,
                      "/fibbing/fibbing-requirement/requirement[%d]/schedule/end-hour", i);
          //
          sprintf(tmpBuff, "\"start-hour\" : \"%.*s\",", start_hour_len, start_hour);
          strcat(buffer, tmpBuff);
          sprintf(tmpBuff, "\"end-hour\" : \"%.*s\",", end_hour_len, end_hour);
          strcat(buffer, tmpBuff);
          strcat(buffer, "\"days\" : [");

          int j,m;
          char pathString[100];
          if(status == fibbing_scheduled) {
            sprintf(pathString,"/fibbing/fibbing-requirement/requirement[%d]/schedule/days", i );
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

          strcat(buffer, "\"requirement\" : [");
          // int j,m;
          // char pathString[100];
          sprintf(pathString,"/fibbing/fibbing-requirement/requirement[%d]/Path", i );
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


    strcat(buffer, "  ]}");


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
        rename(FIBBING_CONFIG_TMP, FIBBING_CONFIG);

      }

    // ***********************************************************
    // create socket

    FILE *fp_out_FIb;
    if ((fp_out_FIb = fopen(Fib_OUT, "w")) == NULL) {
        // return CONFD_ERR;
        printf("eror\n" );
    }

    fprintf(fp_out_FIb, buffer);
    fclose(fp_out_FIb);



    push_configuration(buffer,strlen(buffer), Controller_port);


    return cdb_close(rsock);
}
/********************************************************************/


/********************************************************************/

/********************************************************************/
static int read_conf_Network(struct sockaddr_in *addr)
{
    FILE *fp;
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
    cdb_set_namespace(rsock, fibbing__ns);

    if(DEBUG == 1) {
      // --------------------------------------------------------------------
      // open the config file (create one if not exist yet)
      if ((fp = fopen(TOPOLOGY_CONFIG_TMP, "w")) == NULL) {
          cdb_close(rsock);
          return CONFD_ERR;
      }

    }


    // this will contain the config
    char buffer[MAXREQ*MAXREQSIZE];

    char tmpBuff[200];

    // --------------------------------------------------------------------
    //              GET CONFIGURATION CHANGES of MININET
    // --------------------------------------------------------------------

    // confd_value_t *values;
    sprintf(buffer, "{\"config\" :{ ");

    strcat(buffer,"\"routers\" : [");
    n = cdb_num_instances(rsock, "/fibbing/network/router");
    for(i=0;i<n;i++){
      unsigned char *routername;
      int routername_len;
      cdb_get_buf(rsock, &routername, &routername_len,
                  "/fibbing/network/router[%d]/name", i);
      //
      char star[20];
      if(routername_len < 20) {
        sprintf(star, "%.*s", routername_len, routername);
      }

      if (strcmp(star,"*")!=0 ) {

        sprintf(tmpBuff,"{\"name\" :\"%.*s\", ",
          routername_len,routername);
        strcat(buffer,tmpBuff);
        strcat(buffer,"\"ospf\" : {");
        int r_ospf_enable;
        cdb_get_bool(rsock, &r_ospf_enable, "/fibbing/network/router[%d]/ospf/enable", i);
        struct in_addr router_id;
        if(r_ospf_enable == 1) {
          cdb_get_ipv4(rsock, &router_id, "/fibbing/network/router[%d]/ospf/router-id", i);
          strcat(buffer,"\"enable\" : true,");
          sprintf(tmpBuff, "\"router-id\" : \"%s\"}", inet_ntoa(router_id));
          strcat(buffer,tmpBuff);
        } else if(r_ospf_enable == 0) {
          strcat(buffer,"\"enable\" : false ,\"router-id\" : \"\"}");
        }
        strcat(buffer, "}"); // closing router obj {name :

        if(i != n-1) {
          strcat(buffer,",");
        }

      }
    }
    strcat(buffer,"],"); // routers

    strcat(buffer,"\"links\": [");
    n = cdb_num_instances(rsock, "/fibbing/network/link");
    for(i=0;i<n;i++){
      unsigned char *src_name;
      int src_name_len;
      cdb_get_buf(rsock, &src_name, &src_name_len,
                  "/fibbing/network/link[%d]/src/name", i);
      //

      unsigned char *link_name;
      int link_name_len;
      cdb_get_buf(rsock, &link_name, &link_name_len,
                  "/fibbing/network/link[%d]/name", i);
      //

      unsigned char *dest_name;
      int dest_name_len;
      cdb_get_buf(rsock, &dest_name, &dest_name_len,
                  "/fibbing/network/link[%d]/dest/name", i);
      //
      unsigned char *src_ip;
      int src_ip_len;
      cdb_get_buf(rsock, &src_ip, &src_ip_len,
                  "/fibbing/network/link[%d]/src/ip", i);
      //
      unsigned char *dest_ip;
      int dest_ip_len;
      cdb_get_buf(rsock, &dest_ip, &dest_ip_len,
                  "/fibbing/network/link[%d]/dest/ip", i);
      //
      uint16_t cost;
      int bw;
      cdb_get_int32(rsock, &bw, "/fibbing/network/link[%d]/bw", i );
      cdb_get_u_int16(rsock, &cost, "/fibbing/network/link[%d]/cost", i);

      strcat(buffer,"{\"src\": {");
      sprintf(tmpBuff,"\"name\" :\"%.*s\", ",
        src_name_len,src_name);
      strcat(buffer,tmpBuff);

      sprintf(tmpBuff, "\"ip\" : \"%.*s\"},",src_ip_len, src_ip );
      strcat(buffer,tmpBuff);
      strcat(buffer,"\"dest\": {");
      sprintf(tmpBuff,"\"name\" :\"%.*s\", ",
        dest_name_len,dest_name);
      strcat(buffer,tmpBuff);

      sprintf(tmpBuff, "\"ip\" : \"%.*s\"},", dest_ip_len, dest_ip);
      strcat(buffer,tmpBuff);
      sprintf(tmpBuff, "\"bw\" : %d,\"cost\" : %d,", bw, cost);
      strcat(buffer,tmpBuff);
      sprintf(tmpBuff,"\"name\" :\"%.*s\"} ",
        link_name_len,link_name);
      strcat(buffer,tmpBuff);




      if(i != n-1) {
        strcat(buffer,",");
      }
    }
    strcat(buffer,"],"); // links

    strcat(buffer,"\"ospf-links\": [");
    n = cdb_num_instances(rsock, "/fibbing/network/ospf-link-config");
    for(i=0;i<n;i++){
      unsigned char *link_name;
      int link_name_len;
      cdb_get_buf(rsock, &link_name, &link_name_len,
                  "/fibbing/network/ospf-link-config[%d]/link-name", i);
      //

      uint16_t src_hello_interval, src_dead_interval;
      cdb_get_u_int16(rsock, &src_hello_interval, "/fibbing/network/ospf-link-config[%d]/src/hello-interval", i);
      cdb_get_u_int16(rsock, &src_dead_interval, "/fibbing/network/ospf-link-config[%d]/src/dead-interval", i);

      // get lsa config
      uint8_t intf_delay, intf_initial_holdtime, intf_max_holdtime;
      uint16_t  intf_min_ls_arrival, intf_min_ls_interaval;
      cdb_get_u_int8(rsock, &intf_delay, "/fibbing/network/ospf-link-config[%d]/src/throttle/delay",i);
      cdb_get_u_int8(rsock, &intf_initial_holdtime, "/fibbing/network/ospf-link-config[%d]/src/throttle/initial_holdtime",i);
      cdb_get_u_int8(rsock, &intf_max_holdtime, "/fibbing/network/ospf-link-config[%d]/src/throttle/max_holdtime",i);
      cdb_get_u_int16(rsock, &intf_min_ls_arrival, "/fibbing/network/ospf-link-config[%d]/src/lsa/min_ls_arrival",i);
      cdb_get_u_int16(rsock, &intf_min_ls_interaval, "/fibbing/network/ospf-link-config[%d]/src/lsa/min_ls_interval",i);
      struct in_addr intf_area;
      cdb_get_ipv4(rsock, &intf_area, "/fibbing/network/ospf-link-config[%d]/src/area",i);

      sprintf(tmpBuff,"{\"name\" :\"%.*s\", ",
        link_name_len,link_name);
      strcat(buffer,tmpBuff);

      strcat(buffer,"\"src\": {");
      strcat(buffer,"\"ospf\": {");
      sprintf(tmpBuff, "\"hello-interval\" : %d,\"dead-interval\" : %d,\n",
                src_hello_interval, src_dead_interval);
      strcat(buffer,tmpBuff);

      sprintf(tmpBuff, "\"area\" : \"%s\",", inet_ntoa(intf_area));
      strcat(buffer,tmpBuff);

      strcat(buffer, "\"throttle\" : {");
      sprintf(tmpBuff, "\"delay\" : %d ,", intf_delay);
      strcat(buffer,tmpBuff);
      sprintf(tmpBuff, "\"initial_holdtime\" : %d ,", intf_initial_holdtime);
      strcat(buffer,tmpBuff);
      sprintf(tmpBuff, "\"max_holdtime\" : %d },", intf_max_holdtime);
      strcat(buffer,tmpBuff);

      strcat(buffer, "\"lsa\" : {");
      sprintf(tmpBuff, "\"min_ls_arrival\" : %d ,", intf_min_ls_arrival);
      strcat(buffer,tmpBuff);
      sprintf(tmpBuff, "\"min_ls_interval\" : %d}}", intf_min_ls_interaval);
      strcat(buffer,tmpBuff);
      strcat(buffer,"},"); // src


      uint16_t dest_hello_interval, dest_dead_interval;
      cdb_get_u_int16(rsock, &dest_hello_interval, "/fibbing/network/ospf-link-config[%d]/dest/hello-interval", i);
      cdb_get_u_int16(rsock, &dest_dead_interval, "/fibbing/network/ospf-link-config[%d]/dest/dead-interval", i);

      // get lsa config
      uint8_t intf_delay_dest, intf_initial_holdtime_dest, intf_max_holdtime_dest;
      uint16_t  intf_min_ls_arrival_dest, intf_min_ls_interaval_dest;
      cdb_get_u_int8(rsock, &intf_delay_dest, "/fibbing/network/ospf-link-config[%d]/dest/throttle/delay",i);
      cdb_get_u_int8(rsock, &intf_initial_holdtime_dest, "/fibbing/network/ospf-link-config[%d]/dest/throttle/initial_holdtime",i);
      cdb_get_u_int8(rsock, &intf_max_holdtime_dest, "/fibbing/network/ospf-link-config[%d]/dest/throttle/max_holdtime",i);
      cdb_get_u_int16(rsock, &intf_min_ls_arrival_dest, "/fibbing/network/ospf-link-config[%d]/dest/lsa/min_ls_arrival",i);
      cdb_get_u_int16(rsock, &intf_min_ls_interaval_dest, "/fibbing/network/ospf-link-config[%d]/dest/lsa/min_ls_interval",i);
      struct in_addr intf_area_dest;
      cdb_get_ipv4(rsock, &intf_area_dest, "/fibbing/network/ospf-link-config[%d]/dest/area",i);



      strcat(buffer,"\"dest\": {");
      strcat(buffer,"\"ospf\": {");
      sprintf(tmpBuff, "\"hello-interval\" : %d,\"dead-interval\" : %d,\n",
                dest_hello_interval, dest_dead_interval);
      strcat(buffer,tmpBuff);

      sprintf(tmpBuff, "\"area\" : \"%s\",", inet_ntoa(intf_area_dest));
      strcat(buffer,tmpBuff);

      strcat(buffer, "\"throttle\" : {");
      sprintf(tmpBuff, "\"delay\" : %d ,", intf_delay_dest);
      strcat(buffer,tmpBuff);
      sprintf(tmpBuff, "\"initial_holdtime\" : %d ,", intf_initial_holdtime_dest);
      strcat(buffer,tmpBuff);
      sprintf(tmpBuff, "\"max_holdtime\" : %d },", intf_max_holdtime_dest);
      strcat(buffer,tmpBuff);

      strcat(buffer, "\"lsa\" : {");
      sprintf(tmpBuff, "\"min_ls_arrival\" : %d ,", intf_min_ls_arrival_dest);
      strcat(buffer,tmpBuff);
      sprintf(tmpBuff, "\"min_ls_interval\" : %d}}", intf_min_ls_interaval_dest);
      strcat(buffer,tmpBuff);
      strcat(buffer,"}"); // dest
      strcat(buffer,"}");// name


      if(i != n-1) {
        strcat(buffer,",");
      }
    }
    strcat(buffer,"],"); // ospf-links


    strcat(buffer,"\"fibbing-controller\" :{ "); // fibbing-controller
    strcat(buffer,"\"links\" : [");

    n = cdb_num_instances(rsock, "/fibbing/network/fibbing-controller/links");
    for(i=0;i<n;i++){
      unsigned char *ctrl_name;
      int ctrl_name_len;
      cdb_get_buf(rsock, &ctrl_name, &ctrl_name_len,
                  "/fibbing/network/fibbing-controller/links[%d]/controller/name", i);
      //
      unsigned char *r_name;
      int r_name_len;
      cdb_get_buf(rsock, &r_name, &r_name_len,
                  "/fibbing/network/fibbing-controller/links[%d]/router/name", i);
      //
      unsigned char *ctrl_ip;
      int ctrl_ip_len;
      cdb_get_buf(rsock, &ctrl_ip, &ctrl_ip_len,
                  "/fibbing/network/fibbing-controller/links[%d]/controller/ip", i);
      //
      unsigned char *r_ip;
      int r_ip_len;
      cdb_get_buf(rsock, &r_ip, &r_ip_len,
                  "/fibbing/network/fibbing-controller/links[%d]/router/ip", i);
      //
      int bw;
      cdb_get_int32(rsock, &bw, "/fibbing/network/fibbing-controller/links[%d]/bw", i );
      strcat(buffer,"{\"controller\": {");
      sprintf(tmpBuff,"\"name\" :\"%.*s\", ",
        ctrl_name_len,ctrl_name);
      strcat(buffer,tmpBuff);

      sprintf(tmpBuff, "\"ip\" : \"%.*s\"},",ctrl_ip_len , ctrl_ip);
      strcat(buffer,tmpBuff);
      strcat(buffer,"\"router\": {");
      sprintf(tmpBuff,"\"name\" :\"%.*s\", ",
        r_name_len,r_name);
      strcat(buffer,tmpBuff);

      sprintf(tmpBuff, "\"ip\" : \"%.*s\"},",r_ip_len , r_ip);
      strcat(buffer,tmpBuff);
      sprintf(tmpBuff, "\"bw\" : %d}",bw);
      strcat(buffer,tmpBuff);

      if(i != n-1) {
        strcat(buffer,",");
      }
    }
    strcat(buffer,"],"); // links

    strcat(buffer,"\"controller-config\": {"); // links
    uint16_t c_hello_interval, c_dead_interval;
    cdb_get_u_int16(rsock, &c_hello_interval,
      "/fibbing/network/fibbing-controller/controller-config/ospf-config/hello-interval");
    cdb_get_u_int16(rsock, &c_dead_interval,
      "/fibbing/network/fibbing-controller/controller-config/ospf-config/dead-interval");

    // get lsa config
    uint8_t intf_delay_c, intf_initial_holdtime_c, intf_max_holdtime_c;
    uint16_t  intf_min_ls_arrival_c, intf_min_ls_interaval_c;
    cdb_get_u_int8(rsock, &intf_delay_c,
      "/fibbing/network/fibbing-controller/controller-config/ospf-config/throttle/delay");
    cdb_get_u_int8(rsock, &intf_initial_holdtime_c,
      "/fibbing/network/fibbing-controller/controller-config/ospf-config/throttle/initial_holdtime");
    cdb_get_u_int8(rsock, &intf_max_holdtime_c,
      "/fibbing/network/fibbing-controller/controller-config/ospf-config/throttle/max_holdtime");
    cdb_get_u_int16(rsock, &intf_min_ls_arrival_c,
      "/fibbing/network/fibbing-controller/controller-config/ospf-config/lsa/min_ls_arrival");
    cdb_get_u_int16(rsock, &intf_min_ls_interaval_c,
      "/fibbing/network/fibbing-controller/controller-config/ospf-config/lsa/min_ls_interval");
    struct in_addr intf_area_c;
    cdb_get_ipv4(rsock, &intf_area_c,
      "/fibbing/network/fibbing-controller/controller-config/ospf-config/area");

    strcat(buffer,"\"ospf\": {");
    sprintf(tmpBuff, "\"hello-interval\" : %d,\"dead-interval\" : %d,\n",
              c_hello_interval, c_dead_interval);
    strcat(buffer,tmpBuff);

    sprintf(tmpBuff, "\"area\" : \"%s\",", inet_ntoa(intf_area_c));
    strcat(buffer,tmpBuff);

    strcat(buffer, "\"throttle\" : {");
    sprintf(tmpBuff, "\"delay\" : %d ,", intf_delay_c);
    strcat(buffer,tmpBuff);
    sprintf(tmpBuff, "\"initial_holdtime\" : %d ,", intf_initial_holdtime_c);
    strcat(buffer,tmpBuff);
    sprintf(tmpBuff, "\"max_holdtime\" : %d },", intf_max_holdtime_c);
    strcat(buffer,tmpBuff);

    strcat(buffer, "\"lsa\" : {");
    sprintf(tmpBuff, "\"min_ls_arrival\" : %d,", intf_min_ls_arrival_c);
    strcat(buffer,tmpBuff);
    sprintf(tmpBuff, "\"min_ls_interval\" : %d}},", intf_min_ls_interaval_c);
    strcat(buffer,tmpBuff);


    struct confd_ipv4_prefix private_ip;
    cdb_get_ipv4prefix(rsock, &private_ip,
                "/fibbing/network/fibbing-controller/controller-config/private-ip-prefix");
    //

    struct confd_ipv4_prefix base_net_ip;
    cdb_get_ipv4prefix(rsock, &base_net_ip,
                "/fibbing/network/fibbing-controller/controller-config/base-net-perfix");
    //

    sprintf(tmpBuff, "\"private-ip-prefix\" : \"%s/%d\",", inet_ntoa(private_ip.ip), private_ip.len);
    strcat(buffer,tmpBuff);

    sprintf(tmpBuff, "\"base-net-perfix\" : \"%s/%d\"", inet_ntoa(base_net_ip.ip), base_net_ip.len);
    strcat(buffer,tmpBuff);

    strcat(buffer,"}"); // controller-config
    strcat(buffer,"},"); // fibbing-controller


    strcat(buffer,"\"hosts-link\" : [");

    n = cdb_num_instances(rsock, "/fibbing/network/hosts-link");
    for(i=0;i<n;i++){
      unsigned char *host_name;
      int host_name_len;
      cdb_get_buf(rsock, &host_name, &host_name_len,
                  "/fibbing/network/hosts-link[%d]/host/name", i);
      //

      unsigned char *r_name;
      int r_name_len;
      cdb_get_buf(rsock, &r_name, &r_name_len,
                  "/fibbing/network/hosts-link[%d]/router/name", i);
      //

      unsigned char *host_ip;
      int host_ip_len;
      cdb_get_buf(rsock, &host_ip, &host_ip_len,
                  "/fibbing/network/hosts-link[%d]/host/ip", i);
      //

      unsigned char *r_ip;
      int r_ip_len;
      cdb_get_buf(rsock, &r_ip, &r_ip_len,
                  "/fibbing/network/hosts-link[%d]/router/ip", i);
      //
      int bw;
      cdb_get_int32(rsock, &bw, "/fibbing/network/hosts-link[%d]/bw", i );
      strcat(buffer,"{\"host\" : {");
      sprintf(tmpBuff,"\"name\" :\"%.*s\", ",
        host_name_len,host_name);
      strcat(buffer,tmpBuff);
      sprintf(tmpBuff, "\"ip\" : \"%.*s\"},",  host_ip_len,host_ip);
      strcat(buffer,tmpBuff);

      strcat(buffer,"\"router\" : {");
      sprintf(tmpBuff,"\"name\" :\"%.*s\", ",
        r_name_len,r_name);
      strcat(buffer,tmpBuff);
      sprintf(tmpBuff, "\"ip\" : \"%.*s\"},",  r_ip_len,  r_ip);
      strcat(buffer,tmpBuff);
      sprintf(tmpBuff, "\"bw\" : %d", bw);
      strcat(buffer,tmpBuff);
      strcat(buffer,"}");

      if(i != n-1) {
        strcat(buffer,",");
      }
    }
    strcat(buffer,"],"); // hosts-links

    unsigned char *main_ctrl;
    int main_ctrl_len;
    cdb_get_buf(rsock, &main_ctrl, &main_ctrl_len,
                "/fibbing/network/main-controller");
    //
    sprintf(tmpBuff,"\"main-controller\" :\"%.*s\" ",
      main_ctrl_len,main_ctrl);
    strcat(buffer,tmpBuff);







    strcat(buffer, "\n}}"); // end of {config :{
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

    FILE *fp_out_topo;
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
    cdb_set_namespace(rsock, fibbing__ns);
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
            sprintf(Path, "/fibbing/fibbing-requirement/requirement{%s}/state", tmp);

            int status = cdb_exists(rsock, Path);
            if(status != CONFD_ERR && status == 1) {
              printf("\n>>>> key : %s\n", tmp);
              char KEY[MAXREQSIZE];
              sprintf(KEY,"%s", tmp);
              strcpy( keys[key_index], KEY);
              if (key_index+2 > MAXREQ) {
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
    if (argc ==2 && argv[1][0]=='1' ){
      printf("************ DEBUG : 1\n"  );
      DEBUG = 1;
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
    if ((status = cdb_subscribe(subsock, 3, fibbing__ns, &spoint, "/fibbing"))
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
                                        "/fibbing/fibbing-requirement") == CONFD_OK) {

                  printf("Modifications to subscription committed:\n");
                  print_modifications(values, nvalues, NULL, 0,&addr,keys);
                  printf("******** \n >> Fibbing requirement : %d\n", nvalues);

                  if(nvalues != 0) {

                    //------------------------------------------------
                      if ((status = read_conf_Fibbing(&addr, keys)) != CONFD_OK) {
                          fprintf(stderr, "Terminate: read_conf %d\n", status);
                          exit(1);
                      }

                  }

                  for (i = 0; i < nvalues; i++)
                      confd_free_value(CONFD_GET_TAG_VALUE(&values[i]));
                  free(values);

                  for(i=0; i< MAXREQ; i++) {
                    // reseting all keys
                    strcpy( keys[i], "");
                  }

                  OVERLOAD = 0;
              }

              if (cdb_get_modifications(subsock, sub_points[0], flags, &values, &nvalues,
                                        "/fibbing/network") == CONFD_OK) {


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
