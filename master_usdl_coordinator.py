#The purpose of this file is to combine multiple pieces of equipment into intuitive tools
import sys
sys.path.append("../utoronto_demo")
from North_Safe import North_Robot
from North_Safe import North_Track
from North_Safe import North_Temp
from North_Safe import North_Powder
import pandas as pd
import os
from datetime import datetime

class Lash_E:
    nr_robot = None
    nr_track = None
    cytation = None
    photoreactor = None
    temp_controller = None
    powder_dispenser = None
    simulate = None

    def __init__(self, vial_file, initialize_robot=True,initialize_track=True,initialize_biotek=True,initialize_t8=False,initialize_p2=False,simulate=False,logging=False,logging_folder="../utoronto_demo/logs"):
        
        self.simulate = simulate
        self.log_file = None
        self.original_stdout = None
        self.original_stderr = None

        if logging:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            os.makedirs(logging_folder, exist_ok=True)
            self.log_file_path = os.path.join(logging_folder, f"experiment_log_{timestamp}_sim{simulate}.txt")
            self.log_file = open(self.log_file_path, "w")
            self.original_stdout = sys.stdout
            self.original_stderr = sys.stderr
            sys.stdout = sys.stderr = self.log_file

        if not simulate:
            from north import NorthC9
            c9 = NorthC9("A", network_serial="AU06CNCF")
        else:
            from unittest.mock import MagicMock
            c9 = MagicMock()

        if initialize_robot:
            self.nr_robot = North_Robot(c9, vial_file,simulate=simulate)

        if initialize_biotek:
            from biotek_new import Biotek_Wrapper
            self.cytation = Biotek_Wrapper(simulate=simulate)
        
        if initialize_track:
            self.nr_track = North_Track(c9, simulate=simulate)
        

        # Photoreactor initialization
        if not self.simulate:
            from photoreactor_controller import Photoreactor_Controller
            self.photoreactor = Photoreactor_Controller()

            if initialize_p2:
                self.powder_dispenser = North_Powder(c9)
            if initialize_t8:
                self.temp_controller = North_Temp(c9)
            if initialize_track:
                self.nr_track = North_Track(c9)

        else:
            from unittest.mock import MagicMock
            self.photoreactor = MagicMock()
            self.powder_dispenser = MagicMock()
            self.temp_controller = MagicMock()
            #self.nr_track = MagicMock(c9)

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.log_file:
            sys.stdout = self.original_stdout
            sys.stderr = self.original_stderr
            self.log_file.close()

    def mass_dispense_into_vial(self,vial,mass_mg,channel=0, return_home=True):
        self.nr_robot.move_vial_to_location(vial,'clamp',0)
        self.nr_robot.move_home()
        self.powder_dispenser.dispense_powder_mg(mass_mg=mass_mg,channel=channel) #Dispense 50 mg of solid into source_vial_a  
        if return_home:
            self.nr_robot.return_vial_home(vial) 

    def move_wellplate_to_cytation(self,wellplate_index=0,quartz=False,plate_type="96 WELL PLATE"):
        self.nr_track.grab_well_plate_from_nr(wellplate_index,quartz_wp=quartz)
        self.nr_track.move_gripper_to_cytation()
        if not self.simulate:
            self.cytation.CarrierOut()
        self.nr_track.release_well_plate_in_cytation(quartz_wp=quartz)
        if not self.simulate:
            self.cytation.CarrierIn(plate_type=plate_type)

    def move_wellplate_back_from_cytation(self,wellplate_index=0,quartz=False,plate_type="96 WELL PLATE"):
        if not self.simulate:
            self.cytation.CarrierOut()
        self.nr_track.grab_well_plate_from_cytation(quartz_wp=quartz)
        if not self.simulate:
            self.cytation.CarrierIn(plate_type=plate_type)
        self.nr_track.return_well_plate_to_nr(wellplate_index,quartz_wp=quartz)  

    def measure_wellplate(self,protocol_file_path=None,wells_to_measure=None,wellplate_index=0,quartz=False,plate_type="96 WELL PLATE",repeats=1):
        """
        Move wellplate to the Cytation for plate reader measurements.

        Args:
            protocol_file_path (str): Path to the measurement protocol file.
            wells_to_measure (list or range): Indices of the wells to measure.
            wellplate_index (int): Index of where the wellplate is stored.
            quartz (bool): Whether the wellplate is a quartz plate.
            plate_type (str): Type of the plate (e.g., "96 WELL PLATE").
            repeats (int): How many times to repeat the measurement.
        
        Returns:
            pd.DataFrame: Combined measurement data.
                        - If repeats == 1: regular columns (e.g., '600')
                        - If repeats > 1: MultiIndex columns (e.g., ('rep1', '600'))
        """
        self.nr_robot.move_home()
        self.move_wellplate_to_cytation(wellplate_index, quartz=quartz, plate_type=plate_type)

        all_data = []
        if not self.simulate and protocol_file_path is not None:
            for i in range(repeats):
                print(f"Running protocol {protocol_file_path} (rep {i+1})")
                data = self.cytation.run_protocol(protocol_file_path, wells_to_measure, plate_type=plate_type)
                if data is not None:
                    if repeats > 1:
                        # Add replicate label as top-level MultiIndex
                        data.columns = pd.MultiIndex.from_tuples([(f"rep{i+1}", col) for col in data.columns])
                    all_data.append(data)

            if all_data:
                combined_data = pd.concat(all_data, axis=1)
            else:
                combined_data = None
        else:
            combined_data = None

        self.move_wellplate_back_from_cytation(wellplate_index, quartz=quartz, plate_type=plate_type)
        self.nr_track.origin()
        return combined_data

    def run_photoreactor(self,vial_index,target_rpm,intensity,duration,reactor_num):
        self.nr_robot.move_vial_to_location(vial_index,'photoreactor_array',reactor_num)
        self.photoreactor.run_photoreactor(target_rpm,duration,intensity,reactor_num)
        self.nr_robot.return_vial_home(vial_index)

    def grab_new_wellplate(self):
        self.nr_robot.move_home()
        self.nr_track.get_new_wellplate(move_home_afterwards=True)
    
    def discard_used_wellplate(self):
        self.nr_robot.move_home()
        self.nr_track.discard_wellplate(move_home_afterwards=True)