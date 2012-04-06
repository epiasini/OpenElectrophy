# -*- coding: utf-8 -*-
"""
This implements a high level object for spike sorting.

It is contructed to manipulate to neo object, 
see here for details: http://packages.python.org/neo/usecases.html

The main idea is we have a set of state during the spike sorting
and spiksorter methods can switch the obejct from one state to the other.

Current states are:
  1. Full band raw signals
  2. Filtered signals
  3. Detected spike times
  4. Aligned spike waveforms
  5. Projected spike waveforms
  6. Cluster definition/estimation
  7. Spikes (all) attributed to clusters
  [8. Spike are attributed probalistically to clusters] Experimental

Traditional work flow was: 
  * full band: 1->2->3->4->5->7
  * filtered band: 2->3->4->5->7
  * from detected spikes: 4->5->7
  
New methods can switch from arbitrary states. Examples:
  * Franke: 2->7
  * STO method: 1->4
  * Wood: 1->8
  * MCMC: 5->8(->7)

Each class from the spike sorting framework must take the spikesorter as input,
implement a single method that switches from one state to another.
A typical computing class must:
  * declare doc for ref (bibliographic)
  * give initial and final states
  * propose a single computing method that takes the SpikeSorter itself as input

Of course all OE0.2 methods can be clearly reimplemented here:
  * filtering 1->2
  * detection 2->3
  * extraction 3->4
  * ...

At creation time, spikesorter must be initialized with a given state.

All spike sorting steps can be traced and applied directly to another RecordingChannelGroup

SpikeSorter must be well adapted both to script and GUI.

"""

import copy

class SpikeSorter():
    """
    
    
    Example::
    
        from OpenElectrophy.spikesorting import (generate_dataset, SpikeSorter,
                           ButterworthFiltering , StdThreshold, AlignWaveformOnPeak,
                            PcaProjection, GaussianMixtureEm)
            
        recordingChannelGroup = generate_dataset()
        spikesorter = SpikeSorter(recordingChannelGroup, initialState='fullBandSignal')
        
        # Apply a chain
        spikesorting.computeStep( ButterworthFilter, f_low = 300.)
        spikesorting.computeStep( StdThreshold,sign= '-', std_thresh = 5)
        spikesorting.computeStep(AlignWaveformOnPeak   , left_sweep = 2*pq.ms , right_sweep = 5*pq.ms)
        spikesorting.computeStep(PcaFeature   , ndim = 5)
        spikesorting.computeStep(SklearnGaussianMixtureEm   , )
        
        
        
        
        
    
    
    """
    def __init__(self,recordingChannelGroup,initialState='fullBandSignal'):
        """
        
        """
        self.recordingChannelGroup=recordingChannelGroup
        self.state=initialState
        self.history=[ ]
        
        # Each state comes with its own variables:
        
        # NbRC : number of neo.RecordingChannel inside this neo.RecordingChannelGroup
        # NbSeg : numer of neo.Segment inside neo.Block
        # NbSpk : number tatal of detected spikes
        # NbClus : number of cluster
        
        # 1. Full band raw signals
        self.fullBandAnaSig=None # 2D numpy array of objects that points towards neo.AnalogSignal
                                            # shape = (NbRC, NbSeg) 
        # 2. Filtered signals
        self.filteredBandAnaSig=None # 2D numpy array of objects that points towards neo.AnalogSignal
                                            # shape = (NbRC, NbSeg) 
        # 3. Detected spike times
        self.spikeIndexArray = None # 1D np.array of object that point themself to np.array of indices, int64
                                                        #shape = (NbSeg,)
        
        # After that point data are concatenated in compact arrays
        # even if they come from different segment for efficiency reason, PCA need arrays compact)
        # so we need a dictionnary of size NbSeg that have key=neo.Segment and value=a slice
        # to go back from the compact array (spikeWaveforms,spikeWaveformFeatures, spikeClusters, ...)
        # to individual segments
        self.segmentToSpikesMembership = None
        
        # 4. Aligned spike waveforms
        self.spikeWaveforms = None # 3D np.array (dtype float) that concatenate all detected spikes waveform
                                                         # shape = (NbSpk, trodness, nb_point)
                                                         # this can be sliced by self.spikeMembership for splitting back to original neo.Segment
        self.waveformSamplingRate = None # samplingrate of theses waveform
        self.leftSweep = None # nb point on left for that sweep
        self.rightSweep = None # nb point on right for that sweep (this could be a propertis!)
        # self.spikeWaveforms.shape[2] = self.leftSweep+ 1 + self.rightSweep
        
        
        # 5. Projected spike waveforms
        self.spikeWaveformFeatures = None # 2D np.array (dtype=float) to handle typical PCA or wavelet projecttion
                                                            # shape = (NbSpk, ndimension)
        self.featureNames = None # an np.array (dtype = unicode) that handle label of each feature
                                                    # ex: ['pca1', 'pca2', 'pca3', 'pca4'] or ['max_amplitude', 'peak_to valley', ]
                                                    # shape = (ndimension, )
        
        #6. Cluster definition/estimation/after learning
        # this state is not very precise in our mind now
        # this could be 'list of template waveform' or 'cluster centroid + covariance' of gaussian or ..
        # this is method dependant and to be discuss
        
        # 7. Spikes (all) attributed to clusters
        self.spikeClusters = None # 1D np.array (dtype in) to handle wich spijke belong to wich cluster
                                                    # shape = (NbSpk, )
        self.clusterNames = { } # a dict of possible clusters ( keys = unique(self.spikeClusters)
        
        # 8. Spike are attributed probalistically to clusters
        self.spikeClustersProbabilistic = None # A 2D that give for each spike the probality to belong to a cluster
                                                                    #shape = ( NbSpk, NbClus)
        
        
        
        self.initializeState(self.recordingChannelGroup, self.state)
        

        
        
    def initializeState(self,recordingChannelGroup, state):
        if state=='fullBandSignal':
            pass # self.fullBandAnaSig = TODO...
        elif state=='filteredBandSignal':
            pass # self.filteredBandAnaSig = TODO...
        # And so on
    
    
    def computeStep(self, methodClass, **kargs):
        """
        
        Arguments:
            * methodClass: one of the class offered by the framework
            * **kargs: parameter specific to that class
        
        
        
        """
        
        methodInstance = methodClass()
        
        step = dict(
                        methodInstance = methodInstance,# we keep trace of the instance because some method need to be continued like  MCMC (10000 loop, a view, 5000 loop a second viwe...)
                        
                        arguments = copy.deepcopy(kargs), 
                        starting_time = datetime.datetime.now()
                        )
        
        self.history.append(step)
        
        
        methodInstance.compute(spikesorter = self, **kargs)
        
        
        step['end_time'] = datetime.datetime.now()
        
        return step

    def purge_histort(self):
        self.history = [ ]
        
    def applyHistoryToOther(self, other):
        
        for step in history:
            other.computeStep(step['methodInstance'].__class__, **step['arguments'])
            
            
        
        

