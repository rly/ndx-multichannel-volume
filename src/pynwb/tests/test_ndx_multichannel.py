import datetime
import numpy as np
import pandas as pd

from pynwb import NWBHDF5IO, NWBFile
from pynwb.core import DynamicTableRegion
from pynwb.device import Device
from pynwb.ecephys import ElectrodeGroup
from pynwb.file import ElectrodeTable as get_electrode_table
from pynwb.testing import TestCase, remove_test_file, AcquisitionH5IOMixin

from ndx_multichannel_volume import CElegansSubject, OpticalChannelReferences, OpticalChannelPlus, ImagingVolume, VolumeSegmentation, MultiChannelVolume

def set_up_nwbfile():

    nwbfile = NWBFile(
        session_description = 'session_description',
        identifier = 'identifier',
        session_start_time = datetime.datetime.now(),
        lab = 'lab',
        institution = 'institution'
    )

    device = nwbfile.create_device(
        name='device_name'
    )

    return nwbfile, device

def create_im_vol(device, channels, location="head", grid_spacing=[0.3208, 0.3208, 0.75], grid_spacing_unit ="micrometers", origin_coords=[0,0,0], origin_coords_unit="micrometers", reference_frame="Worm head, left=anterior, bottom=ventral"):

    # channels should be ordered list of tuples (name, description)

    OptChannels = []
    OptChanRefData = []
    for name, wave in channels:
        excite = float(wave.split('-')[0])
        emiss_mid = float(wave.split('-')[1])
        emiss_range = float(wave.split('-')[2][:-1])
        OptChan = OpticalChannelPlus(
            name = name,
            description = wave,
            excitation_lambda = excite,
            excitation_range = [excite, excite],
            emission_range = [emiss_mid-emiss_range/2, emiss_mid+emiss_range/2],
            emission_lambda = emiss_mid
        )

        OptChannels.append(OptChan)
        OptChanRefData.append(OptChan)

    OpticalChannelRefs = OpticalChannelReferences(
        name = 'Order_optical_channels',
        data = OptChanRefData
    )

    imaging_vol = ImagingVolume(
        name= 'ImagingVolume',
        optical_channel_plus = OptChannels,
        Order_optical_channels = OpticalChannelRefs,
        description = 'NeuroPAL image of C elegan brain',
        device = device,
        location = location,
        grid_spacing = grid_spacing,
        grid_spacing_unit = grid_spacing_unit,
        origin_coords = origin_coords,
        origin_coords_unit = origin_coords_unit,
        reference_frame = reference_frame
    )

    return imaging_vol, OpticalChannelRefs, OptChannels

class TestMultiChannelVolumeConstructor(TestCase):

    def setUp(self):
        self.nwbfile, self.device = set_up_nwbfile()

    def test_constructor(self):
        """Test that the constructor for each object sets values as expected."""
        data = np.random.randint(0,100,size=(240,1000,50,5))
        scale = [0.25, 0.3, 1.0]
        session_start = datetime.datetime.now()

        self.nwbfile.subject = CElegansSubject(
            subject_id = 'ID',
            growth_stage_time = pd.Timedelta(hours=2, minutes=30).isoformat(),
            growth_stage = 'YA',
            cultivation_temp = 20.,
            description = 'description',
            species = "caenorhabditis elegans",
            sex = "XX"
        )

        channels = [("mNeptune 2.5", "561-700-75m"), ("Tag RGP-T", "561-605-70m")]

        reference_frame = 'reference'

        self.ImagingVol, self.OptChannelRefs, self.OpticalChannelPlus = create_im_vol(self.device, channels, location = "head", grid_spacing= scale, reference_frame = reference_frame)

        self.volume_seg = VolumeSegmentation(
            name = 'VolumeSegmentation',
            description = 'Neuron centers',
            imaging_volume = self.ImagingVol
        )

        blobs = pd.DataFrame(np.random.randint(0,100,size=(10,4)), columns=['X', 'Y', 'Z', 'ID'])

        voxel_mask = []

        for i, row in blobs.iterrows():
            x = row['X']
            y = row['Y']
            z = row['Z']
            ID = row['ID']

            voxel_mask.append([np.uint(x),np.uint(y),np.uint(z),1,str(ID)])

        self.volume_seg.add_roi(voxel_mask=voxel_mask)

        RGBW_channels = [0,4,2,1]

        self.image = MultiChannelVolume(
            name = 'multichanvol',
            resolution = scale,
            description = 'description',
            RGBW_channels = RGBW_channels,
            data = data,
            imaging_volume = self.ImagingVol
        )

        self.nwbfile.add_acquisition(self.image)

        neuroPAL_module = self.nwbfile.create_processing_module(
            name = 'NeuroPAL',
            description = 'description'
        )

        neuroPAL_module.add(self.volume_seg)
        neuroPAL_module.add(self.ImagingVol)
        # neuroPAL_module.add(self.OptChannelRefs)
        # neuroPAL_module.add(self.OpticalChannelPlus)

        self.assertEqual(self.image.name, 'multichanvol')
        self.assertEqual(self.image.resolution, scale)
        self.assertEqual(self.image.description, 'description')
        self.assertEqual(self.image.RGBW_channels, RGBW_channels)
        self.assertEqual(self.image.name, 'multichanvol')
        self.assertContainerEqual(self.image.imaging_volume, self.ImagingVol)
        np.testing.assert_array_equal(self.image.data, data)

        self.assertEqual(self.nwbfile.subject.growth_stage_time, pd.Timedelta(hours=2, minutes=30).isoformat())
        self.assertEqual(self.nwbfile.subject.growth_stage, "YA")
        self.assertEqual(self.nwbfile.subject.cultivation_temp, 20.)
        self.assertEqual(self.nwbfile.subject.growth_stage, "YA")

        self.assertEqual(self.ImagingVol.name, "ImagingVolume")
        self.assertEqual(self.ImagingVol.description, "NeuroPAL image of C elegan brain")
        self.assertEqual(self.ImagingVol.location, "head")
        self.assertEqual(self.ImagingVol.reference_frame, reference_frame)
        self.assertEqual(self.ImagingVol.grid_spacing, scale)
        self.assertContainerEqual(self.ImagingVol.optical_channel_plus[0], self.OpticalChannelPlus[0])
        self.assertContainerEqual(self.ImagingVol.optical_channel_plus[1], self.OpticalChannelPlus[1])
        self.assertContainerEqual(self.ImagingVol.Order_optical_channels, self.OptChannelRefs)

        for i, row in blobs.iterrows():
            self.assertEqual(self.volume_seg.voxel_mask[i][0], row['X'])
            self.assertEqual(self.volume_seg.voxel_mask[i][1], row['Y'])
            self.assertEqual(self.volume_seg.voxel_mask[i][2], row['Z'])
            self.assertEqual(self.volume_seg.voxel_mask[i][4], str(row['ID']))
        self.assertContainerEqual(self.volume_seg.imaging_volume, self.ImagingVol)

        for i, chan in enumerate(self.OpticalChannelPlus):
            #self.assertEqual(chan.name, channels[i][0])
            wave = channels[i][1]
            excite = float(wave.split('-')[0])
            emiss_mid = float(wave.split('-')[1])
            emiss_range = float(wave.split('-')[2][:-1])
            self.assertEqual(chan.description, wave)
            self.assertEqual(chan.excitation_lambda, excite)
            self.assertEqual(chan.excitation_range, [excite, excite])
            self.assertEqual(chan.emission_range, [emiss_mid-emiss_range/2, emiss_mid+emiss_range/2])
            self.assertEqual(chan.emission_lambda, emiss_mid)

            self.assertEqual(self.OptChannelRefs.data[i], chan)

class TestMultiChannelVolumeRoundtrip(TestCase):

    def setUp(self):
        self.nwbfile, self.device = set_up_nwbfile()
        self.path = 'test.nwb'

    def tearDown(self):
        remove_test_file(self.path)

    def test_roundtrip(self):
        """Test that the constructor for each object sets values as expected."""
        data = np.random.randint(0,100,size=(240,1000,50,5))
        scale = [0.25, 0.3, 1.0]
        session_start = datetime.datetime.now()

        self.nwbfile.subject = CElegansSubject(
            subject_id = 'ID',
            growth_stage_time = pd.Timedelta(hours=2, minutes=30).isoformat(),
            growth_stage = 'YA',
            cultivation_temp = 20.,
            description = 'description',
            species = "caenorhabditis elegans",
            sex = "XX"
        )

        channels = [("mNeptune 2.5", "561-700-75m")]

        reference_frame = 'reference'

        self.ImagingVol, self.OptChannelRefs, self.OpticalChannelPlus = create_im_vol(self.device, channels, location = "head", grid_spacing= scale, reference_frame = reference_frame)

        self.volume_seg = VolumeSegmentation(
            name = 'VolumeSegmentation',
            description = 'Neuron centers',
            imaging_volume = self.ImagingVol
        )

        blobs = pd.DataFrame(np.random.randint(0,100,size=(10,4)), columns=['X', 'Y', 'Z', 'ID'])

        voxel_mask = []

        for i, row in blobs.iterrows():
            x = row['X']
            y = row['Y']
            z = row['Z']
            ID = row['ID']

            voxel_mask.append([np.uint(x),np.uint(y),np.uint(z),1,str(ID)])

        self.volume_seg.add_roi(voxel_mask=voxel_mask)

        RGBW_channels = [0,4,2,1]

        self.image = MultiChannelVolume(
            name = 'multichanvol',
            resolution = scale,
            description = 'description',
            RGBW_channels = RGBW_channels,
            data = data,
            imaging_volume = self.ImagingVol
        )

        self.nwbfile.add_acquisition(self.image)

        neuroPAL_module = self.nwbfile.create_processing_module(
            name = 'NeuroPAL',
            description = 'description'
        )

        neuroPAL_module.add(self.volume_seg)
        neuroPAL_module.add(self.ImagingVol)
        # neuroPAL_module.add(self.OptChannelRefs)
        # neuroPAL_module.add(self.OpticalChannelPlus)

        with NWBHDF5IO(self.path, mode='w') as io:
            io.write(self.nwbfile)

        with NWBHDF5IO(self.path, mode='r', load_namespaces=True) as io:
            read_nwbfile = io.read()
            self.assertContainerEqual(self.image, read_nwbfile.acquisition['multichanvol'])
            self.assertContainerEqual(self.ImagingVol, read_nwbfile.processing['NeuroPAL']['ImagingVolume'])
            self.assertContainerEqual(self.volume_seg, read_nwbfile.processing['NeuroPAL']['VolumeSegmentation'])
            self.assertContainerEqual(self.OptChannelRefs, read_nwbfile.processing['NeuroPAL']['ImagingVolume'].Order_optical_channels)

        self.tearDown()

