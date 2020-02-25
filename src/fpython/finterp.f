chelp+
      !--------------------------------------
      ! subroutine to interpolate missing data. 
      ! The data must be band limited for the 
      ! method to work reliably. 
      ! Method: 
      !     1. FFT the data after zeroing the 
      !        BAD points.
      !     2. Apply a gaussian filter to taper 
      !        down high frequencies
      !     3. Inverse transform back
      !     4. Replace the good points with the 
      !        original data. 
      !     5. Iterate... 
      !     * Only the missing/bad data get 
      !       modified. The original good data 
      !       remains as they were. 
      !
      !          --wr, 09 May, 2018
      !
      ! Last Modification:
      !     * FlagArr is now passed with 1 indicating
      !       valid data and 0 indicating bad data.
      !       The fit is done using ONLY the valid data
      !     * Additionally one may use the "maskVal"
      !       to further NOT USE masked data in the
      !       FFT-based interpolation.
      !     * At the the end of the routine, the FlagArr
      !       is replaced with 1's provided the
      !       refAnt parameter is set to 0.
      !     * refAnt additionally allows user to decide
      !       if any interpolation needs to be done at all.
      !       If refAnt is set to 1, this routine does
      !       no interpolation and returns OutArr = InArr.
      !       The FlagArr is also returned unchanged.
      !--------------------------------------
chelp-


      subroutine finterp(InArr,FlagArr,maskVal,npts,nTaper,niter,refAnt,
     -                    OutArr)

              implicit none

              integer*4, intent(in) :: npts, nTaper, niter, refAnt
              real*4, intent(in),dimension(npts) :: InArr 
              real*4, intent(in) :: maskVal 
              real*4, intent(out),dimension(npts) :: OutArr
              real*4, intent(inout),dimension(npts) ::  FlagArr

              integer*4     i, iter  
              real*4        xarr(npts) 
              real*4        tol,diff  

              external lowpass

              if (refAnt .eq. 1)then
                      do i = 1,npts
                         OutArr(i) = InArr(i)
                         FlagArr(i) = FlagArr(i)
                      enddo
                      return
              endif

              tol = 1.0e-6 

              iter = 0
              do i =1,npts 
                 diff = abs(InArr(i) - maskVal)
                 if (diff .lt. tol)then 
                         FlagArr(i) = 0.0
                         iter = iter + 1
                 endif
                 OutArr(i) = InArr(i)*FlagArr(i)
              enddo 
              write(*,*)"Points masked during interp stage: ",iter

              do iter = 1,niter
                do i = 1,npts
                   xarr(i) = OutArr(i)
                enddo 
                call lowpass(xarr, npts, nTaper, OutArr)
                ! Replace the good data with original:
                do i = 1,npts 
                   if(FlagArr(i) .eq. 1.0)then 
                           OutArr(i) = InArr(i) 
                   endif
                enddo 
              enddo 
              ! Assume all points are valid now, and make the FLagArr
              ! all 1's:
              do i =1,npts
                 FlagArr(i) = 1.0
              enddo

      return 

      end subroutine 

      include 'lowpass.f'
      !include 'fort_lib.f'
      include 'FFT/fft1d.f'
      include 'FFT/ifft1d.f'
      include 'FFT/fft_general_lin.f'

