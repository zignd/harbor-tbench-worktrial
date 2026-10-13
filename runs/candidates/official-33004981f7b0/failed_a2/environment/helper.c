#include <stdio.h>
#include <string.h>
#include <openssl/sha.h>
int main(int argc,char **argv){char a[4096],b[4096]; unsigned char z=0,h[32]; if(argc==3){strncpy(a,argv[1],sizeof(a)-1);strncpy(b,argv[2],sizeof(b)-1);} else if(argc==1){if(!fgets(a,sizeof(a),stdin)||!fgets(b,sizeof(b),stdin))return 2; a[strcspn(a,"\r\n")]=0;b[strcspn(b,"\r\n")]=0;} else return 2; SHA256_CTX c;SHA256_Init(&c);SHA256_Update(&c,a,strlen(a));SHA256_Update(&c,&z,1);SHA256_Update(&c,b,strlen(b));SHA256_Final(h,&c);for(int i=0;i<32;i++)printf("%02x",h[i]);putchar('\n');return 0;}
