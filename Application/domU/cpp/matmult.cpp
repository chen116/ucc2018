// example Custom C++ Application
#include "pacer.h"
// library for sleep function used in this example
#include <unistd.h>


void matmult(int **,int **,int **,int);

void matmult(int ** ptr1,int ** ptr2, int ** ptr3,int N){

    int i, j, k;



    for (i = 0; i < N; i++) {
        for (j = 0; j < N; j++) {
            ptr3[i][j] = 0;
            for (k = 0; k < N; k++)
                ptr3[i][j] = ptr3[i][j] + ptr1[i][k] * ptr2[k][j];
        }
    }

    return;
}


int main(int argc, char** argv)
{
    // create a pacer instant
    Pacer mypacer;
    // set window size for heartbeat and create heartbeat instance
    mypacer.setWindowSize(5);


    int **ptr1, **ptr2, **ptr3;
    int  col1, row2, col2;
    int N=100;
    int j,i;
    ptr1 = (int **) malloc (sizeof (int *) * N);
    ptr2 = (int **) malloc (sizeof (int *) * N);
    ptr3 = (int **) malloc (sizeof (int *) * N);
    for (i = 0; i < N; i++)
        ptr1[i] = (int *) malloc (sizeof (int) * N);
    for (i = 0; i < N; i++)
        ptr2[i] = (int *) malloc (sizeof (int) * N);
    for (i = 0; i < N; i++)
        ptr3[i] = (int *) malloc (sizeof (int) * N);

    for (i = 0; i < N; i++) {
        for (j = 0; j < N; j++) {
            ptr1[i][j] = rand ()%10;
        }
    }

    for (i = 0; i < N; i++) {
        for (j = 0; j < N; j++) {
            ptr2[i][j] = rand ()%10;
        }
    }



    for (i = 0; i < 50; ++i)
    {
        matmult(ptr1,ptr2,ptr3,N);
        matmult(ptr1,ptr2,ptr3,N);



        mypacer.beat();
        // write instant heart rate to xenstore
        mypacer.writeInstantHeartRate();


        // printf("heartbeat: instant rate: %f\n",hb_get_instant_rate(heart) );
    }
        usleep(100000);
    
    for (i = 0; i < 50; ++i)
    {

        matmult(ptr1,ptr2,ptr3,N);
        mypacer.beat();
        // write instant heart rate to xenstore
        mypacer.writeInstantHeartRate();


        // printf("heartbeat: instant rate: %f\n",hb_get_instant_rate(heart) );
    }
    


    printf("done\n");
    return 0;
}