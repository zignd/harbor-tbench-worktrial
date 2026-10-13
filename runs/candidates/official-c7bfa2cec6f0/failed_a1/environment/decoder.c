#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
int main(void){uint32_t r;uint16_t n,m;if(fread(&r,4,1,stdin)!=1||fread(&n,2,1,stdin)!=1||fread(&m,2,1,stdin)!=1)return 2;double*x=calloc(n,sizeof(double));for(int i=0;i<n;i++){int16_t v;if(fread(&v,2,1,stdin)!=1)return 2;double g=r==2?1.25:r==3?.75:1,o=r==2?-3:r==3?4:0;x[i]=g*v+o;}for(int j=0;j<m;j++){double z=(j+1)*.125;for(int i=0;i<n;i++)z+=((((i+1)*(j+2))%17)-8)*x[i]/9.;fwrite(&z,8,1,stdout);}free(x);return 0;}
