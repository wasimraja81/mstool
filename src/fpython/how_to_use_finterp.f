chelp+
      !--------------------------------------
      ! Driver program for fourier_interp.f
      !          --wr, 23 Nov, 2010
      !--------------------------------------
chelp-


      implicit none

      integer*4     maxpts
      parameter     (maxpts=655360)
      real*4        InArrRe(maxpts), 
     -              OutArrRe(maxpts)
      real*8        flagArr(maxpts)  

      integer*4     npts, niter, nTaper  
      integer*4     i
      character*180 infile
      integer*4     nchar

      ! Plotting related: 
      character*120 xlabel, ylabel, title
      real*4        xarr(maxpts), yarr(maxpts) 
      real*4        xmin, xmax, ymin, ymax 
      real*4        tmpnum, tmpnum1, tmpnum2, maskval 
      character*128 tmpchar 



      if (iargc().lt.4)then 
              write(*,*)"Usage: "
              write(*,*)"how_to_use_finterp <infile> <nTaper> <Niter> <M
     -askval>" 
              stop 
      else
              call getarg(1,infile)
              call getarg(2,tmpchar)
              read(tmpchar,*)nTaper

              call getarg(3,tmpchar)
              read(tmpchar,*)niter

              call getarg(4,tmpchar)
              read(tmpchar,*)maskval
      endif
      !write(*,*)"Input file name(assumed to be in DATA/ dir): "
      !read(*,*)infile
      infile = infile(1:nchar(infile))
      open(21,file=infile,status='old',err=1001)
      goto 1002 
1001  write(*,*)"Error opening file: ",infile(1:nchar(infile))
      stop
1002  continue 
      i = 0
      do while(.true.)
         i = i + 1
         read(21,*,end=1000)tmpnum1,tmpnum,tmpnum2 
         flagArr(i) = tmpnum2 
         InArrRe(i) = tmpnum*tmpnum2
      enddo
1000  continue
      npts = i-1 
      close(21)
!      write(*,*)"Input nTaper, niter, maskval: "
!      read(*,*)nTaper, niter, maskval 

      call finterp(InArrRe, flagArr,maskval, npts, nTaper, niter, 
     -                  0,OutArrRe)

      do i = 1,npts
         xarr(i) = real(i) 
         yarr(i) = InArrRe(i) 
      enddo 
      call minima(xarr,npts,xmin)
      call maxima(xarr,npts,xmax)

      call minima(yarr,npts,ymin)
      call maxima(yarr,npts,ymax)

      call pgbeg(0,'/xs',1,2)

      xlabel = 'Dummy x axis'
      ylabel = 'Y '
      title = 'Original Data'

      call pgsci(8)
      call pgsch(2.0)

      call pgenv(xmin,xmax,ymin,ymax,0,1)
      call pglab(xlabel,ylabel,title)
      call pgsci(2)
      call pgpt(npts,xarr,yarr,1)
      !call pgline(npts,xarr,yarr)

      do i = 1,npts
        yarr(i) = OutArrRe(i)
      enddo
      call minima(yarr,npts,ymin)
      call maxima(yarr,npts,ymax)
      !xlabel = 'Dummy x axis'
      ylabel = 'Y Interpolated'
      title = 'Effect of Fourier Interpolation'

      call pgsci(8)
      call pgenv(xmin,xmax,ymin,ymax,0,1)
      call pglab(xlabel,ylabel,title)
      call pgsci(3)
      call pgpt(npts,xarr,yarr,1)
      !call pgline(npts,xarr,yarr)

      call pgend

      end
      include 'finterp.f'
      include 'nchar.f'
      include 'fort_lib.f'

