import os
import xarray

from mpas_tools.scrip.from_mpas import scrip_from_mpas

from compass.io import symlink
from compass.step import Step


class Scrip(Step):
    """
    A step for creating SCRIP files from the MPAS-Ocean mesh

    with_ice_shelf_cavities : bool
        Whether the mesh includes ice-shelf cavities
    """
    def __init__(self, test_case, restart_filename, with_ice_shelf_cavities):
        """
        Create a new step

        Parameters
        ----------
        test_case : compass.ocean.tests.global_ocean.files_for_e3sm.FilesForE3SM
            The test case this step belongs to

        restart_filename : str
            A restart file from the end of the dynamic adjustment test case to
            use as the basis for an E3SM initial condition

        with_ice_shelf_cavities : bool
            Whether the mesh includes ice-shelf cavities
        """

        super().__init__(test_case, name='scrip', ntasks=1,
                         min_tasks=1, openmp_threads=1)

        self.add_input_file(filename='README', target='../README')
        self.add_input_file(filename='restart.nc',
                            target=f'../{restart_filename}')

        self.with_ice_shelf_cavities = with_ice_shelf_cavities

        self.add_output_file(filename='ocean.scrip.nc')

        if with_ice_shelf_cavities:
            self.add_output_file(filename='ocean.mask.scrip.nc')

    def run(self):
        """
        Run this step of the testcase
        """
        with_ice_shelf_cavities = self.with_ice_shelf_cavities

        with xarray.open_dataset('restart.nc') as ds:
            mesh_short_name = ds.attrs['MPAS_Mesh_Short_Name']
            mesh_prefix = ds.attrs['MPAS_Mesh_Prefix']
            prefix = f'MPAS_Mesh_{mesh_prefix}'
            creation_date = ds.attrs[f'{prefix}_Version_Creation_Date']

        link_dir = f'../assembled_files/inputdata/ocn/mpas-o/{mesh_short_name}'

        try:
            os.makedirs(link_dir)
        except OSError:
            pass

        if with_ice_shelf_cavities:
            nomask_str = '.nomask'
        else:
            nomask_str = ''

        local_filename = 'ocean.scrip.nc'
        scrip_filename = \
            f'ocean.{mesh_short_name}{nomask_str}.scrip.{creation_date}.nc'

        scrip_from_mpas('restart.nc', local_filename)

        symlink(f'../../../../../scrip/{local_filename}',
                f'{link_dir}/{scrip_filename}')

        if with_ice_shelf_cavities:
            local_filename = 'ocean.mask.scrip.nc'
            scrip_mask_filename = \
                f'ocean.{mesh_short_name}.mask.scrip.{creation_date}.nc'
            scrip_from_mpas('restart.nc', local_filename,
                            useLandIceMask=True)

            symlink(f'../../../../../scrip/{local_filename}',
                    f'{link_dir}/{scrip_mask_filename}')
