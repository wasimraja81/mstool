chelp+
      !-------------------------------------------
      ! Routine for interpolating functions using  
      ! zero-padding in the Fourier Domain and
      ! inverse transforming back.
      ! Inherently, Complex functions are assumed; 
      ! in case the function is real, supply the 
      ! imaginary part of the array after filling 
      ! with zeros. 
      ! 
      ! The output over-sampled array although is 
      ! supposed to have npts_input x ofac number 
      ! of elements, we force the number of output 
      ! elements to that power of 2 which just 
      ! exceeds npts_input x ofac. 
      !
      ! Associated codes needed: 
      !     1) FFT_GENERAL package
      !         --> fft1d.f
      !         --> ifft1d.f
      !         --> fft_general_lin.f
      !     2) fort_lib.f
      !     3) nchar.f
      ! 
      !                    --wr, 24 Nov, 2010.
      !-------------------------------------------
chelp-


      subroutine lowpass(InArrRe, npts, nTaper, OutArrRe)

      implicit none


      integer*4, intent(in) ::  npts, nTaper 
      real*4, intent(in),dimension(npts) :: InArrRe 
      real*4, intent(inout),dimension(npts) :: OutArrRe
      real*4     OutArrIm(npts)
      real*4     tmpArrRe(npts), tmpArrIm(npts)
      integer*4  i, n1 

      !-------------------------------

      ! How does one initialise w/o running 
      ! a do-loop? 
      do i = 1,npts
         OutArrRe(i) = 0.0
         OutArrIm(i) = 0.0

         tmpArrRe(i) = InArrRe(i)
         tmpArrIm(i) = 0.0 
      enddo


      call fft1d(tmpArrRe,tmpArrIm,npts)

      if(mod(npts,2).eq.0)then
              n1 = npts/2 
      else
              n1 = (npts-1)/2
      endif

      !====================================
      ! Weigh down high frequencies : 
      do i = 1,n1
         OutArrRe(i) = tmpArrRe(i)*exp(-(1.0-i)**2/(2.0*nTaper**2)) 
         OutArrIm(i) = tmpArrIm(i)*exp(-(1.0-i)**2/(2.0*nTaper**2)) 
      enddo
      do i = n1+1,npts
         OutArrRe(i) = tmpArrRe(i)*exp(-(npts+1.0-i)**2/(2.0*nTaper**2))
         OutArrIm(i) = tmpArrIm(i)*exp(-(npts+1.0-i)**2/(2.0*nTaper**2))
      enddo
      !====================================

      call ifft1d(OutArrRe,OutArrIm,npts)

      return

      end

