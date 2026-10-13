#include <stdio.h>
#include <string.h>
int main(void){char b[256]; while(fgets(b,sizeof b,stdin)){char *p=strchr(b,'\n');if(p)*p=0;if(!strcmp(b,"reset"))puts("OK");else if(!strncmp(b,"tag:",4))printf("route-%s\n",b+4);else puts("ERR");fflush(stdout);}return 0;}
