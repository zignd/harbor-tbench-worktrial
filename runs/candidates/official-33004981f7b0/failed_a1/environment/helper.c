#include <stdio.h>
#include <string.h>
#include <openssl/sha.h>
int main(int n,char**v){unsigned char h[32],z=0;SHA256_CTX c;if(n!=3)return 2;SHA256_Init(&c);SHA256_Update(&c,v[1],strlen(v[1]));SHA256_Update(&c,&z,1);SHA256_Update(&c,v[2],strlen(v[2]));SHA256_Final(h,&c);for(int i=0;i<32;i++)printf("%02x",h[i]);puts("");return 0;}
