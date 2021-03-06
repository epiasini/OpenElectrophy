# -*- coding: utf-8 -*-
"""
Higher level object for computing, ploting and manipulating morlet scalogram.
"""

import numpy as np
import quantities as pq

from scipy import fftpack
#~ import numpy.fft as fftpack

import joblib
from tempfile import mkdtemp
global memory
memory = None


def assume_quantity(v, units = ''):
    if not isinstance(v, pq.Quantity):
        return pq.Quantity(v, units)
    else:
        return v
        


def generate_wavelet_fourier(len_wavelet,
            f_start,
            f_stop,
            deltafreq,
            sampling_rate,
            f0,
            normalisation,
            ):
    """
    Compute the wavelet coefficients at all scales and makes its Fourier transform.
    When different signal scalograms are computed with the exact same coefficients, 
        this function can be executed only once and its result passed directly to compute_morlet_scalogram
        
    Output:
        wf : Fourier transform of the wavelet coefficients (after weighting), Fourier frequencies are the first 
    """
    # compute final map scales
    scales = f0/np.arange(f_start,f_stop,deltafreq)*sampling_rate
    # compute wavelet coeffs at all scales
    xi=np.arange(-len_wavelet/2.,len_wavelet/2.)
    xsd = xi[:,np.newaxis] / scales
    wavelet_coefs=np.exp(complex(1j)*2.*np.pi*f0*xsd)*np.exp(-np.power(xsd,2)/2.)

    weighting_function = lambda x: x**(-(1.0+normalisation))
    wavelet_coefs = wavelet_coefs*weighting_function(scales[np.newaxis,:])

    # Transform the wavelet into the Fourier domain
    #~ wf=fft(wavelet_coefs.conj(),axis=0) <- FALSE
    wf=fftpack.fft(wavelet_coefs,axis=0)
    wf=wf.conj() # at this point there was a mistake in the original script
    
    return wf

def reduce_signal(ana, t_start = None, t_stop = None):
    """
    reduce signal to time limits
    """
    # Reduce signal to time limits
    if t_start is not None:
        ana = ana[ana.times>=t_start]
        ana.t_start = max(t_start, ana.t_start)
    if t_start is not None:
        ana = ana[ana.times<=t_stop]
    return ana

def check_or_get_sampling_rate(ana, f_stop, sampling_rate = None):
    if sampling_rate is None:
        if f_stop*4 < ana.sampling_rate:
            sampling_rate = f_stop*4
        else:
            sampling_rate = ana.sampling_rate
    assert sampling_rate>=2*f_stop
    return sampling_rate

def convolve_scalogram(ana, wf, sampling_rate):
    n = wf.shape[0]
    sig  = ana.magnitude
    sigf=fftpack.fft(sig)
    # subsampling in fft domain (attention factor)
    factor = (sampling_rate/ana.sampling_rate).simplified.magnitude
    sigf = np.concatenate([sigf[0:(n+1)/2],  sigf[-(n-1)/2:]])*factor
    
    # windowing ???
    #win = fftpack.ifftshift(np.hamming(n))
    #sigf *= win
    
    # Convolve (mult. in Fourier space)
    wt_tmp=fftpack.ifft(sigf[:,np.newaxis]*wf,axis=0)
    # and shift
    wt = fftpack.fftshift(wt_tmp,axes=[0])    
    return wt








class TimeFreq():
    """
    *TimeFreq*

    Input:
    ana: neo.AnalogSignal
    f_start, f_stop, deltafreq : Frequency start stop and step at which the scalogram is computed.
    samplingrate : time samplingrate of the scalogram if None sampling_rate = 4*f_stop
    t_start, t_stop : optional time limit (in second)
    f0 : central frequency of the Morlet wavelet.  The Fourier spectrum of
        the Morlet wavelet appears as a Gaussian centered on f0. 
        It is also used as the wavelet characteristic frequency.
        Low f0 favors time precision of the scalogram while high f0 favors frequency precision
    normalisation : positive value favors low frequency components
    
    wf: pre computed wavelet coeef in furrier domain
        if it is not None (by default), it will ignore all other parameters and compute the map 
        assuming wf is the Fourier transform of the wavelet_coefs
    use_joblib: use joblib to cache wf
    
    Output:
        self.map is  scalogram (dtype.complex)
        self.freqs is vector frequency
        self.times is vectors times
    
    Note : this code is a simplification and correction of the full wavelet package (cwt.py)
    orinally proposed by Sean Arms (http://github.com/lesserwhirls)
    
    """
    def __init__(self, ana,
            f_start=5. * pq.Hz,
            f_stop=100.* pq.Hz,
            deltafreq = 1.* pq.Hz,
            sampling_rate = None,
            t_start = None, 
            t_stop = None,
            f0=2.5, 
            normalisation = 0.,
            wf=None,
            use_joblib = True):

        f_start = assume_quantity(f_start, units = 'Hz')
        f_stop = assume_quantity(f_stop, units = 'Hz')
        deltafreq = assume_quantity(deltafreq, units = 'Hz')
        
        self.f_start = f_start
        self.f_stop = f_stop
        self.deltafreq = deltafreq
        self.f0 = f0
        self.normalisation = normalisation
        
        self.orignal_ana = ana
        self.ana = ana = reduce_signal(ana, t_start, t_stop )
        self.sampling_rate = sr = check_or_get_sampling_rate(ana, f_stop, sampling_rate)
        
        
        n = int(ana.size*sr/ana.sampling_rate)
        if n>0:
            if wf is None:
                if use_joblib:
                    global memory
                    if memory is None:
                        cachedir = mkdtemp()
                        memory = joblib.Memory(cachedir=cachedir, verbose = 0)
                    func = memory.cache(generate_wavelet_fourier)
                else:
                    func = generate_wavelet_fourier
                wf = func(n, f_start.magnitude, f_stop.magnitude, deltafreq.magnitude,
                                sr.magnitude, f0, normalisation)
            assert wf.shape[0] == n
            wt = convolve_scalogram(ana, wf, sr)
        else:
            wt = empty((0,scales.size),dtype='complex')
        
        self.map = wt
        
        self.f = self.freqs = np.arange(f_start,f_stop,deltafreq, dtype = 'f8')*pq.Hz
        self.t = self.times = self.ana.t_start + np.arange(self.map.shape[0]) / self.sampling_rate
    
    def mpl_plot(self, ax,
                                    colorbar = True,
                                    cax =None,
                                    orientation='horizontal',
                                    clim = None,
                                    **kargs):
        """
        
        ax : a matplotlib axes
        
        """
        im = ax.imshow(abs(self.map).transpose(),
                                    interpolation='nearest', 
                                    extent=(self.ana.t_start, self.ana.t_stop, self.f_start-self.deltafreq/2., self.f_stop-self.deltafreq/2.),
                                    origin ='lower' ,
                                    aspect = 'normal')
        if clim is not None:
            im.set_clim(clim)
        if colorbar:
            if cax is None:
                ax.figure.colorbar(im)
            else:
                ax.figure.colorbar(im,ax = ax, cax = cax ,orientation=orientation)
            
                
        return im
    plot = mpl_plot




def compute_morlet_scalogram(ana, **kargs):
    """
    Direct methods to comptude scalogram.
    See TimeFreq for kargs.
    
    Keep for old compatibility
    """
    tfr = TimeFreq(ana, **kargs)
    return tfr.map
