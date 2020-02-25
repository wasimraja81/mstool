chelp+ 
! This subroutine is meant for INVERSE 
! Fourier Transforming 2D data.
! It uses the "fft_general_lin.f" routine.
!      
! Requires:
!      1) 'fft2d.inc' file to be included
!      Other subroutines are expected to 
!      be included in the calling program:
!      
!      1) 'fft_general_lin.f' 
!      
! IMPORTANT: 
!       This subroutine modifies the input 
!       arrays to contain the output of 
!       the Fourier Transform.
!
!       This subroutine does the BACKWARD 
!       Transform. In other words, the 
!       argument of the exponential is 
!       taken to be POSITIVE.
!      
!       --wasim raja, 02 Jan, 2010
!-----------------------------------------------------------
chelp-

       subroutine ifft2d(rfx,ifx,npts1,npts2)


       implicit none

       include 'INCLUDE/fft2d.inc'
       real*4 rtmp(maxdimx_fft2d), itmp(maxdimx_fft2d)
       real*4    rfx(maxdimx_fft2d,maxdimy_fft2d)               ! value of function(real) 
       real*4    ifx(maxdimx_fft2d,maxdimy_fft2d)               ! value of function(imag) 
       integer*4 i,j,ierr,npts1, npts2
       real*4    pi

       !integer*4 nshift1, nshift2

       integer*4 nchar


       pi = acos(-1.)

C --------------------------------------------------------------

       !nshift1 = int(npts1/2)
       !nshift2 = int(npts2/2)
       do i = 1,npts1
          do j = 1,npts2
             rtmp(j) = rfx(i,j)
             itmp(j) = ifx(i,j)
          enddo
          !call shift(rtmp,npts2,nshift2)
          !call shift(itmp,npts2,nshift2)

          CALL FFT(rtmp,itmp,1,npts2,1,1,ierr)

          !call shift(rtmp,npts2,nshift2)
          !call shift(itmp,npts2,nshift2)
          do j = 1,npts2
             rfx(i,j) = rtmp(j)
             ifx(i,j) = itmp(j)
          enddo
       enddo

       do i = 1,npts2
          do j = 1,npts1
             rtmp(j) = rfx(j,i)
             itmp(j) = ifx(j,i)
          enddo
          !call shift(rtmp,npts1,nshift1)
          !call shift(itmp,npts1,nshift1)

          CALL FFT(rtmp,itmp,1,npts1,1,1,ierr)

          !call shift(rtmp,npts1,nshift1)
          !call shift(itmp,npts1,nshift1)
          do j = 1,npts1
             rfx(j,i) = rtmp(j)
             ifx(j,i) = itmp(j)
          enddo
       enddo
       return

       end

