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
// #include <pthread.h>

/* include generated file */
#include "sragent.h"
int DEBUG = 0;
int MAXREQ = 500;
int MAXREQSIZE = 20;
int OVERLOAD = 0;

// static int update_status(char *name, int id ) {
//   struct sockaddr_in addr;
//
//   addr.sin_addr.s_addr = inet_addr("127.0.0.1");
//   addr.sin_family = AF_INET;
//   addr.sin_port = htons(CONFD_PORT);
//
//   int rsock ;
//   if ((rsock = socket(PF_INET, SOCK_STREAM, 0)) < 0)
//       confd_fatal(": Failed to create socket");
//   if (cdb_connect(rsock, CDB_DATA_SOCKET, (struct sockaddr *)&addr,
//                   sizeof(struct sockaddr_in)) < 0)
//       confd_fatal(": Failed to connect to ConfD");
//   int ret;
//   if ((ret = cdb_start_session(rsock, CDB_OPERATIONAL)) != CONFD_OK)
//       return ret;
//   if ((ret = cdb_set_namespace(rsock, sragent__ns)) != CONFD_OK)
//       return ret;
//
//
//
//   cdb_delete(rsock,"/sragent/sr-routes[%d]", id);
//   cdb_end_session(rsock);
//   return ret;
// }
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
    cdb_set_namespace(rsock, sragent__ns);

    confd_value_t *values;

    n = cdb_num_instances(rsock, "/sragent/sr-routes");
    for (i=0; i<n; i++) {
        unsigned char  *intf;
        int  intf_len;
        char buffer[200];

        char tmpBuff[200];
        char command[250];
        char Delete[250];
        struct confd_ipv6_prefix dest_ip;
        // GET DESTINATION
        cdb_get_ipv6prefix(rsock, &dest_ip,
                    "/sragent/sr-routes[%d]/destination", i);
        //
        char dest_str[INET6_ADDRSTRLEN];
        inet_ntop(AF_INET6, &(dest_ip.ip6), dest_str, INET6_ADDRSTRLEN);
        char tmp[50];
        sprintf(tmp, "%s/%d",dest_str ,dest_ip.len);


        if( OVERLOAD == 1 || in_keys(keys, tmp) == 1) { // if requirement has changed
          int type;
          cdb_get_enum_value(rsock, &type ,"/sragent/sr-routes[%d]/action", i);


          int l, k;
          l =  cdb_num_instances(rsock, "/sragent/sr-routes[%d]/routes", i);
          if(l == 1) {
            printf("****Single route\n" );
            int j,m;
            char pathString[100];
            sprintf(pathString,"/sragent/sr-routes[%d]/routes[%d]/segments", i, 0 );
            if(CONFD_ERR != cdb_get_list(rsock, &values, &m, pathString)) {
              sprintf(buffer, " ");
              for (j = 0; j < m; j++) {
                  struct in6_addr seg_ip;
                  seg_ip = CONFD_GET_IPV6(&values[j]);

                  char seg_str[INET6_ADDRSTRLEN];
                  inet_ntop(AF_INET6, &(seg_ip), seg_str, INET6_ADDRSTRLEN);

                  if(j== m-1) {

                    sprintf(tmpBuff, "%s", seg_str);
                    strcat(buffer,tmpBuff);
                  } else {

                    sprintf(tmpBuff, "%s,", seg_str);
                    strcat(buffer,tmpBuff);
                  }

                  confd_free_value(&values[j]);
              }
              free(values);

            }

            switch (type) {
              case sragent_add:
                cdb_get_buf(rsock, &intf, &intf_len,
                            "/sragent/sr-routes[%d]/routes[%d]/intf", i, 0 );


                sprintf(command, "ip -6 ro ad %s/%d encap seg6 mode encap segs %s dev %.*s",
                  dest_str,dest_ip.len , buffer, intf_len, intf
                );

                printf(">>>> Add %s\n", command);
                system(command);


                break;


              case sragent_delete:

                sprintf(command, "ip -6 ro del %s/%d",
                  dest_str,dest_ip.len
                );

                printf(">>>> Delete : %s\n", command);

                system(command);
                break;
              case sragent_modify:
                sprintf(command, "ip -6 ro del %s/%d",
                  dest_str,dest_ip.len
                );

                printf(">>>> Delete : %s\n", command);
                system(command);
                cdb_get_buf(rsock, &intf, &intf_len,
                            "/sragent/sr-routes[%d]/routes[%d]/intf", i, 0 );


                sprintf(command, "ip -6 ro ad %s/%d encap seg6 mode encap segs %s dev %.*s",
                  dest_str,dest_ip.len , buffer, intf_len, intf
                );

                printf(">>>> Add %s\n", command);
                system(command);

                break;
              // default:

            }

          } else {
            // Begin command
            sprintf(tmpBuff, " ");
            sprintf(command, " ");
            sprintf(tmpBuff, "ip -6 ro ad %s/%d ",
              dest_str,dest_ip.len );
            strcat(command,tmpBuff);

            // ECMP route
            for(k=0; k <l; k++) {

              // get Segments
              int j,m;
              char pathString[100];
              sprintf(pathString,"/sragent/sr-routes[%d]/routes[%d]/segments", i, k );
              if(CONFD_ERR != cdb_get_list(rsock, &values, &m, pathString)) {
                sprintf(buffer, " ");
                for (j = 0; j < m; j++) {
                    struct in6_addr seg_ip;
                    seg_ip = CONFD_GET_IPV6(&values[j]);

                    char seg_str[INET6_ADDRSTRLEN];
                    inet_ntop(AF_INET6, &(seg_ip), seg_str, INET6_ADDRSTRLEN);

                    if(j== m-1) {

                      sprintf(tmpBuff, "%s", seg_str);
                      strcat(buffer,tmpBuff);
                    } else {

                      sprintf(tmpBuff, "%s,", seg_str);
                      strcat(buffer,tmpBuff);
                    }

                    confd_free_value(&values[j]);
                }
                free(values);

              } // end for j (read segss)
              // get intf
              cdb_get_buf(rsock, &intf, &intf_len,
                          "/sragent/sr-routes[%d]/routes[%d]/intf", i, k );

              //
              sprintf(tmpBuff, " nexthop encap seg6 mode encap segs %s dev %.*s",
                buffer, intf_len, intf
              );
              strcat(command,tmpBuff);

            } // for ECMP route

            //  run the command
            switch (type) {
              case sragent_add:
                printf(">>>> Add %s\n", command);
                system(command);
                break;


              case sragent_delete:

                sprintf(Delete, "ip -6 ro del %s/%d",
                  dest_str,dest_ip.len
                );

                printf(">>>> Delete : %s\n", Delete);

                system(Delete);
                break;
              case sragent_modify:
              sprintf(Delete, "ip -6 ro del %s/%d",
                dest_str,dest_ip.len
              );


                printf(">>>> Delete : %s\n", Delete);
                system(Delete);

                printf(">>>> Add %s\n", command);
                system(command);

                break;
              // default:

            }

          }


        }



    }


    // --------------------------------------------------------------------
    //              FINISH CONFIG
    // --------------------------------------------------------------------


    return cdb_close(rsock);
}
/********************************************************************/
static void print_modifications(confd_tag_value_t *val, int nvals,
                                struct confd_cs_node *start_node,
                                int start_indent,
                                struct sockaddr_in *addr,
                                char keys[MAXREQ][MAXREQSIZE]
                                )
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
    cdb_set_namespace(rsock, sragent__ns);
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
            sprintf(Path, "/sragent/sr-routes{%s}/action", tmp);

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
    if ((status = cdb_subscribe(subsock, 3, sragent__ns, &spoint, "/sragent"))
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
                                        "/sragent") == CONFD_OK) {

                  printf("Modifications to subscription committed:\n");
                  print_modifications(values, nvalues, NULL, 0,&addr,keys);
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
                    strcpy( keys[i], "");
                  }
                  OVERLOAD = 0;

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
