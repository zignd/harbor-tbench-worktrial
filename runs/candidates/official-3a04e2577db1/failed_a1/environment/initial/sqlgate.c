#include <sqlite3.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <ctype.h>
static char cached[4096]; static int cached_result=-1;
static int auth(void *p,int a,const char *x,const char *y,const char *db,const char *z){(void)p;(void)y;(void)db;(void)z; if(a==SQLITE_READ && x && strcmp(x,"telemetry")==0)return SQLITE_OK; if(a==SQLITE_SELECT||a==SQLITE_FUNCTION)return SQLITE_OK; return SQLITE_DENY;}
static char *findstr(const char *s,const char *k){char *p=strstr(s,k); if(!p)return 0; p=strchr(p,':'); if(!p)return 0; while(*++p && (*p==' '||*p=='\"')){}; return p;}
int main(int ac,char **av){const char *db=NULL,*in=NULL,*out=NULL;for(int i=1;i<ac;i++){if(!strcmp(av[i],"--db"))db=av[++i];else if(!strcmp(av[i],"--input"))in=av[++i];else if(!strcmp(av[i],"--output"))out=av[++i];}if(!db||!in)return 2;sqlite3 *c=0; if(sqlite3_open(db,&c))return 2;sqlite3_set_authorizer(c,auth,0);FILE *f=fopen(in,"r"),*o=out?fopen(out,"w"):stdout;if(!f||!o)return 2;char line[65536];while(fgets(line,sizeof line,f)){char *id=findstr(line,"id"),*q=findstr(line,"sql");long n=id?strtol(id,0,10):0;int r=0;if(q){char *e=strchr(q,'\"');if(e){char *t=e+1,*u=strchr(t,'\"');if(u){size_t z=u-t;if(z<sizeof cached){char sql[4096];memcpy(sql,t,z);sql[z]=0;if(!strcmp(sql,cached))r=cached_result;else{sqlite3_stmt *st=0;int x=sqlite3_prepare_v2(c,sql,-1,&st,0);r=(x==SQLITE_OK);if(st)sqlite3_finalize(st);strcpy(cached,sql);cached_result=r;}}}}}fprintf(o,"%ld %s\n",n,r?"ALLOW":"DENY");}fclose(f);if(out)fclose(o);sqlite3_close(c);return 0;}
