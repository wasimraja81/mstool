chelp+ 
      !---------------------------------------------------
      ! This code is intended to read the bptable for 
      ! making useful plots and also detecting solution
      ! outliers, smoothing etc. for refining the 
      ! bandpass solutions. 
      ! 
      ! This code is external to ASKAPsoft. The goal 
      ! would be to import a sister version in c++
      ! 
      !                         --wr, 21 Sep, 2016 
      !---------------------------------------------------
chelp- 
      ! * Last Modification: Change cps to vcps in pgbeg
      !                      to allow ps file in portrait. 
      !                              --wr, 26 Jun, 2017
      ! 
      ! * Last Modification: Made code compatible for f2py 
      !                      to compile. This allows this 
      !                      subroutine to be called from 
      !                      python. 
      !       * Dependent Codes adapted:
      !                      1. mov_poly_harm_fit
      !                      2. poly_harm_fit
      !                              --wr, 19 Apr, 2018 
      !---------------------------------------------------

      subroutine process_bptab(inArr,flagArr,maskVal,npts,nSampPerFit,
     -                   nStagger, nPoly,nHarm,refAnt,outArr)


      !implicit none 
      integer*4, intent(in) :: npts  
      integer*4, intent(in) :: refAnt
      real*4, intent(in),dimension(npts) :: inArr 
      real*4, intent(out),dimension(npts) :: outArr 
      integer*4, intent(in) :: nSampPerFit,nStagger,nPoly, nHarm 
      real*4, intent(in) :: maskVal
      real*4, intent(inout),dimension(npts) :: flagArr
      integer*4         nchar 
      real*4            tol 
      external mov_poly_harm_fit

      ! Set up parameters for the poly_harm_fitting: 
      !nSampPerFit = npts !1024*4 
      !nStagger = int(nSampPerFit/2) !int(nSampPerFit/16)
      !nPoly = 2
      !nHarm = 4
      thresh = 3.0 
      tol = 1.0e-6
      if (refAnt .eq. 1)then
              ! do no fitting
              do ichan = 1,npts
                 OutArr(ichan) = inArr(ichan)
                 flagArr(ichan) = flagArr(ichan)
              enddo
              return
      endif
      iter = 0
      do ichan = 1,npts
         diff = abs(inArr(ichan) - maskVal)
         if (diff .lt. tol)then ! Additional Mask
                 flagArr(ichan) = 0.0
                 iter = iter + 1
         endif
         outArr(ichan) = InArr(ichan)*flagArr(ichan)
      enddo
      write(*,*)"Points masked during fitting: ",iter
      !======================================================= 
      
      ! Interpolate bandpass solutions: 
      ! Smooth representation of inArr: 
      call mov_poly_harm_fit(inArr,ichan,flagArr,
     -                      nSampPerFit,nStagger,nPoly, 
     -                      nHarm, thresh, outArr) 



      end subroutine 
      !include 'myfit_lib.f'
      include 'mov_poly_harm_fit.f'
      include 'poly_harm_fit.f'
      include 'nchar.f'




