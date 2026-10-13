#include <sqlite3.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
static char cached[4096]; static int cached_result=-1;
static int auth(void *p,int a,const char *x,const char *y,const char *db,const char *z){(void)p;(void)y;(void)db;(void)z; if(a==SQLITE_READ&&x&&strcmp(x,"telemetry")==0)return SQLITE_OK; if(a==SQLITE_SELECT||a==SQLITE_FUNCTION)return SQLITE_OK; return SQLITE_DENY;}
static char *findstr(char *s,const char *k){char *p=strstr(s,k);if(!p)return 0;p=strchr(p,':');return p?p+1:0;}
int main(int ac,char **av){const char*db=0,*in=0,*out=0;for(int i=1;i<ac;i++){if(!strcmp(av[i],"--db")&&i+1<ac)db=av[++i];else if(!strcmp(av[i],"--input")&&i+1<ac)in=av[++i];else if(!strcmp(av[i],"--output")&&i+1<ac)out=av[++i];}if(!db||!in)return 2;sqlite3*c=0;if(sqlite3_open(db,&c))return 2;sqlite3_set_authorizer(c,auth,0);FILE*f=fopen(in,"r"),*o=out?fopen(out,"w"):stdout;if(!f||!o)return 2;char line[65536];while(fgets(line,sizeof line,f)){char*q=findstr(line,"\"sql\"");long id=0;char*i=findstr(line,"\"id\"");if(i)id=strtol(i,0,10);int r=0;if(q){q=strchr(q,'\"');if(q){q++;char*e=strchr(q,'\"');if(e){*e=0;if(strcmp(q,cached)==0)r=cached_result;else{sqlite3_stmt*s=0;r=sqlite3_prepare_v2(c,q,-1,&s,0)==SQLITE_OK;if(s)sqlite3_finalize(s);strncpy(cached,q,sizeof(cached)-1);cached_result=r;}}}}fprintf(o,"%ld %s\n",id,r?"ALLOW":"DENY");}fclose(f);if(out)fclose(o);sqlite3_close(c);return 0;}
