import numpy as np
import xarray as xr
import matplotlib.pyplot as plt
import warnings

from compass.step import Step


class Analysis(Step):
    """
    A step for visualizing the output from the cosine bell test case

    Attributes
    ----------
    resolutions : list of int
        The resolutions of the meshes that have been run

    icosahedral : bool
        Whether to use icosahedral, as opposed to less regular, JIGSAW
        meshes
    """
    def __init__(self, test_case, resolutions, icosahedral):
        """
        Create the step

        Parameters
        ----------
        test_case : compass.ocean.tests.global_convergence.cosine_bell.CosineBell
            The test case this step belongs to

        resolutions : list of int
            The resolutions of the meshes that have been run

        icosahedral : bool
            Whether to use icosahedral, as opposed to less regular, JIGSAW
            meshes
        """
        super().__init__(test_case=test_case, name='analysis')
        self.resolutions = resolutions
        self.icosahedral = icosahedral

        for resolution in resolutions:
            if icosahedral:
                mesh_name = f'Icos{resolution}'
            else:
                mesh_name = f'QU{resolution}'
            self.add_input_file(
                filename=f'{mesh_name}_namelist.ocean',
                target=f'../{mesh_name}/init/namelist.ocean')
            self.add_input_file(
                filename=f'{mesh_name}_init.nc',
                target=f'../{mesh_name}/init/initial_state.nc')
            self.add_input_file(
                filename=f'{mesh_name}_output.nc',
                target=f'../{mesh_name}/forward/output.nc')

        self.add_output_file('convergence.png')

    def run(self):
        """
        Run this step of the test case
        """
        plt.switch_backend('Agg')
        resolutions = self.resolutions
        xdata = list()
        ydata = list()
        for res in resolutions:
            if self.icosahedral:
                mesh_name = f'Icos{res}'
            else:
                mesh_name = f'QU{res}'
            rmseValue, nCells = self.rmse(mesh_name)
            xdata.append(nCells)
            ydata.append(rmseValue)
        xdata = np.asarray(xdata)
        ydata = np.asarray(ydata)

        p = np.polyfit(np.log10(xdata), np.log10(ydata), 1)
        conv = abs(p[0]) * 2.0

        yfit = xdata ** p[0] * 10 ** p[1]

        plt.loglog(xdata, yfit, 'k')
        plt.loglog(xdata, ydata, 'or')
        plt.annotate('Order of Convergence = {}'.format(np.round(conv, 3)),
                     xycoords='axes fraction', xy=(0.3, 0.95), fontsize=14)
        plt.xlabel('Number of Grid Cells', fontsize=14)
        plt.ylabel('L2 Norm', fontsize=14)
        plt.savefig('convergence.png', bbox_inches='tight', pad_inches=0.1)

        section = self.config['cosine_bell']
        if self.icosahedral:
            conv_thresh = section.getfloat('icos_conv_thresh')
            conv_max = section.getfloat('icos_conv_max')
        else:
            conv_thresh = section.getfloat('qu_conv_thresh')
            conv_max = section.getfloat('qu_conv_max')

        if conv < conv_thresh:
            raise ValueError(f'order of convergence '
                             f' {conv} < min tolerence {conv_thresh}')

        if conv > conv_max:
            warnings.warn(f'order of convergence '
                          f'{conv} > max tolerence {conv_max}')

    def rmse(self, mesh_name):
        """
        Compute the RMSE for a given resolution

        Parameters
        ----------
        mesh_name : str
            The name of the mesh

        Returns
        -------
        rmseValue : float
            The root-mean-squared error

        nCells : int
            The number of cells in the mesh
        """

        config = self.config
        latCent = config.getfloat('cosine_bell', 'lat_center')
        lonCent = config.getfloat('cosine_bell', 'lon_center')
        radius = config.getfloat('cosine_bell', 'radius')
        psi0 = config.getfloat('cosine_bell', 'psi0')
        pd = config.getfloat('cosine_bell', 'vel_pd')

        init = xr.open_dataset(f'{mesh_name}_init.nc')
        # find time since the beginning of run
        ds = xr.open_dataset(f'{mesh_name}_output.nc')
        for j in range(len(ds.xtime)):
            tt = str(ds.xtime[j].values)
            tt.rfind('_')
            DY = float(tt[10:12]) - 1
            if DY == pd:
                sliceTime = j
                break
        HR = float(tt[13:15])
        MN = float(tt[16:18])
        t = 86400.0 * DY + HR * 3600. + MN
        # find new location of blob center
        # center is based on equatorial velocity
        R = init.sphere_radius
        distTrav = 2.0 * 3.14159265 * R / (86400.0 * pd) * t
        # distance in radians is
        distRad = distTrav / R
        newLon = lonCent + distRad
        if newLon > 2.0 * np.pi:
            newLon -= 2.0 * np.pi

        # construct analytic tracer
        tracer = np.zeros_like(init.tracer1[0, :, 0].values)
        latC = init.latCell.values
        lonC = init.lonCell.values
        temp = R * np.arccos(np.sin(latCent) * np.sin(latC) +
                             np.cos(latCent) * np.cos(latC) * np.cos(
            lonC - newLon))
        mask = temp < radius
        tracer[mask] = psi0 / 2.0 * (
                    1.0 + np.cos(3.1415926 * temp[mask] / radius))

        # oad forward mode data
        tracerF = ds.tracer1[sliceTime, :, 0].values
        rmseValue = np.sqrt(np.mean((tracerF - tracer)**2))

        init.close()
        ds.close()
        return rmseValue, init.dims['nCells']
