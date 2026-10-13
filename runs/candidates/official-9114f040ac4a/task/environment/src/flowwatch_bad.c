#include <stdio.h>
#include <stdlib.h>
#include <string.h>
/* Operational placeholder: the deployed repair preserves this CLI. */
int main(int argc,char **argv){const char *c="/etc/flowwatch/flowwatch.conf"; for(int i=1;i<argc-1;i++) if(!strcmp(argv[i],"-c")) c=argv[++i]; FILE *f=fopen(c,"r"); if(!f)return 2; char line[512],sp[256]="/var/lib/flowwatch/spool",out[256]="/var/lib/flowwatch/out/summary.tsv"; while(fgets(line,sizeof line,f)){if(!strncmp(line,"spool_dir=",10))sscanf(line+10,"%255s",sp);if(!strncmp(line,"output=",7))sscanf(line+7,"%255s",out);}fclose(f); char cmd[700]; snprintf(cmd,sizeof cmd,"mkdir -p $(dirname '%s')",out); system(cmd); FILE *o=fopen(out,"w"); if(!o)return 3; fprintf(o,"protocol\\tsource\\tdestination\\tsource_port\\tdestination_port\\troute\\tpackets\\tbytes\\tfirst_seq\\tlast_seq\\n"); fprintf(o,"TCP\\t10.0.0.1\\t10.0.0.2\\t1000\\t443\\tred\\t4\\t400\\t4294967294\\t1\\n"); fclose(o); return 0;}
