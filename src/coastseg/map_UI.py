# standard python imports
import os
import datetime
import logging
from typing import Callable
from collections import defaultdict

# internal python imports
from coastseg import exception_handler

# external python imports
import ipywidgets
from IPython.display import display
from ipyfilechooser import FileChooser

from google.auth import exceptions as google_auth_exceptions
from ipywidgets import Button
from ipywidgets import ToggleButton
from ipywidgets import HBox
from ipywidgets import VBox
from ipywidgets import Layout
from ipywidgets import DatePicker
from ipywidgets import HTML
from ipywidgets import RadioButtons
from ipywidgets import BoundedFloatText
from ipywidgets import Text
from ipywidgets import SelectMultiple
from ipywidgets import Output

logger = logging.getLogger(__name__)

# icons sourced from https://fontawesome.com/v4/icons/


def create_file_chooser(callback: Callable[[FileChooser], None], title: str = None):
    """
    This function creates a file chooser and a button to close the file chooser.
    It takes a callback function and an optional title as arguments.
    It only searches for .geojson files.

    Args:
        callback (Callable[[FileChooser],None]): A callback function that which is called
        when a file is selected.
        title (str): Optional title for the file chooser.

    Returns:
        chooser (HBox): A HBox containing the file chooser and close button.
    """
    padding = "0px 0px 0px 5px"  # upper, right, bottom, left
    # creates a unique instance of filechooser and button to close filechooser
    geojson_chooser = FileChooser(os.getcwd())
    geojson_chooser.dir_icon = os.sep
    geojson_chooser.filter_pattern = ["*.geojson"]
    geojson_chooser.title = "<b>Select a geojson file</b>"
    if title is not None:
        geojson_chooser.title = f"<b>{title}</b>"
    # callback function is called when a file is selected
    geojson_chooser.register_callback(callback)

    close_button = ToggleButton(
        value=False,
        tooltip="Close File Chooser",
        icon="times",
        button_style="primary",
        layout=Layout(height="28px", width="28px", padding=padding),
    )

    def close_click(change):
        if change["new"]:
            geojson_chooser.close()
            close_button.close()

    close_button.observe(close_click, "value")
    chooser = HBox([geojson_chooser, close_button], layout=Layout(width="100%"))
    return chooser


class UI:
    # all instances of UI will share the same debug_view
    # this means that UI and coastseg_map must have a 1:1 relationship
    # Output widget used to print messages and exceptions created by CoastSeg_Map
    debug_view = Output(layout={"border": "1px solid black"})
    # Output widget used to print messages and exceptions created by download progress
    download_view = Output(layout={"border": "1px solid black"})

    def __init__(self, coastseg_map):
        # save an instance of coastseg_map
        self.coastseg_map = coastseg_map
        # button styles
        self.remove_style = dict(button_color="red")
        self.load_style = dict(button_color="#69add1")
        self.action_style = dict(button_color="#ae3cf0")
        self.save_style = dict(button_color="#50bf8f")
        self.clear_stlye = dict(button_color="#a3adac")

        # buttons to load configuration files
        self.load_configs_button = Button(
            description="Load Config", icon="fa-files-o", style=self.load_style
        )
        self.load_configs_button.on_click(self.on_load_configs_clicked)
        self.save_config_button = Button(
            description="Save Config", icon="fa-floppy-o", style=self.save_style
        )
        self.save_config_button.on_click(self.on_save_config_clicked)

        self.load_file_instr = HTML(
            value="<h2>Load Feature from File</h2>\
                 Load a feature onto map from geojson file.\
                ",
            layout=Layout(padding="0px"),
        )

        self.load_file_radio = RadioButtons(
            options=["Shoreline", "Transects", "Bbox", "ROIs"],
            value="Shoreline",
            description="",
            disabled=False,
        )
        self.load_file_button = Button(
            description=f"Load {self.load_file_radio.value} file",
            icon="fa-file-o",
            style=self.load_style,
        )
        self.load_file_button.on_click(self.load_feature_from_file)

        def change_load_file_btn_name(change):
            self.load_file_button.description = f"Load {str(change['new'])} file"

        self.load_file_radio.observe(change_load_file_btn_name, "value")

        # Generate buttons
        self.gen_button = Button(
            description="Generate ROI", icon="fa-globe", style=self.action_style
        )
        self.gen_button.on_click(self.gen_roi_clicked)
        self.download_button = Button(
            description="Download Imagery", icon="fa-download", style=self.action_style
        )
        self.download_button.on_click(self.download_button_clicked)
        self.extract_shorelines_button = Button(
            description="Extract Shorelines", style=self.action_style
        )
        self.extract_shorelines_button.on_click(self.extract_shorelines_button_clicked)
        self.compute_transect_button = Button(
            description="Compute Transects", style=self.action_style
        )
        self.compute_transect_button.on_click(self.compute_transect_button_clicked)
        self.save_transect_csv_button = Button(
            description="Save Transects CSV", style=self.action_style
        )
        self.save_transect_csv_button.on_click(
            self.on_save_cross_distances_button_clicked
        )
        # Remove buttons
        self.clear_debug_button = Button(
            description="Clear TextBox", style=self.clear_stlye
        )
        self.clear_debug_button.on_click(self.clear_debug_view)

        # create the HTML widgets containing the instructions
        self._create_HTML_widgets()
        self.roi_slider_instr = HTML(value="<b>Choose Area of ROIs</b>")
        # controls the ROI units displayed
        self.units_radio = RadioButtons(
            options=["m²", "km²"],
            value="m²",
            description="Select Units:",
            disabled=False,
        )
        # create two float text boxes that will control size of ROI created
        self.sm_area_textbox = BoundedFloatText(
            value=1500000,
            min=0,
            max=980000000,
            step=1000,
            description="Small ROI Area(m²):",
            style={"description_width": "initial"},
            disabled=False,
        )
        self.lg_area_textbox = BoundedFloatText(
            value=2200000,
            min=0,
            max=980000000,
            step=1000,
            description="Large ROI Area(m²):",
            style={"description_width": "initial"},
            disabled=False,
        )

        # called when unit radio button is clicked
        def units_radio_changed(change):
            """
            Change the maximum area allowed and the description of the small and large ROI area
            textboxes when the units radio is changed. When the units for area is m² the max ROI area size
            is 980000000 and when the units for area is m² max ROI area size
            is 98.

            Parameters:
            change (dict): event dictionary fired by clicking the units_radio button
            """
            try:
                MAX_AREA = 980000000
                # index 0: m², 1:km²
                index = change["old"]["index"]
                # change to index 0 m²
                if index == 0:
                    MAX_AREA = 980000000
                    # change to index 1 m²
                elif index == 1:
                    MAX_AREA = 98
                print(MAX_AREA)
                self.sm_area_textbox.max = MAX_AREA
                self.lg_area_textbox.max = MAX_AREA
                self.sm_area_textbox.description = (
                    f"Small ROI Area({self.units_radio.value}):"
                )
                self.lg_area_textbox.description = (
                    f"Large ROI Area({self.units_radio.value}):"
                )
            except Exception as e:
                print(e)

        # when units radio button is clicked updated units for area textboxes
        self.units_radio.observe(units_radio_changed)

    def get_view_settings_vbox(self) -> VBox:
        # update settings button
        update_settings_btn = Button(
            description="Refresh Settings", icon="fa-refresh", style=self.action_style
        )
        update_settings_btn.on_click(self.update_settings_btn_clicked)
        self.settings_html = HTML()
        self.settings_html.value = self.get_settings_html(self.coastseg_map.settings)
        view_settings_vbox = VBox([self.settings_html, update_settings_btn])
        return view_settings_vbox

    def get_settings_section(self):
        # declare settings widgets
        dates_vbox = self.get_dates_picker()
        satellite_radio = self.get_satellite_radio()
        sand_dropbox = self.get_sand_dropbox()
        min_length_sl_slider = self.get_min_length_sl_slider()
        beach_area_slider = self.get_beach_area_slider()
        shoreline_buffer_slider = self.get_shoreline_buffer_slider()
        cloud_slider = self.get_cloud_slider()
        alongshore_distance_slider = self.get_alongshore_distance_slider()
        pansharpen_toggle = self.get_pansharpen_toggle()
        cloud_theshold_slider = self.get_cloud_threshold_slider()

        settings_button = Button(
            description="Save Settings", icon="fa-floppy-o", style=self.action_style
        )
        settings_button.on_click(self.save_settings_clicked)
        self.output_epsg_text = Text(value="4326", description="Output epsg:")

        # create settings vbox
        settings_vbox = VBox(
            [
                dates_vbox,
                satellite_radio,
                self.output_epsg_text,
                sand_dropbox,
                min_length_sl_slider,
                beach_area_slider,
                shoreline_buffer_slider,
                cloud_slider,
                alongshore_distance_slider,
                cloud_theshold_slider,
                pansharpen_toggle,
                settings_button,
            ]
        )
        return settings_vbox

    def get_dates_picker(self):
        # Date Widgets
        self.start_date = DatePicker(
            description="Start Date",
            value=datetime.date(2018, 12, 1),
            disabled=False,
        )
        self.end_date = DatePicker(
            description="End Date",
            value=datetime.date(2019, 3, 1),  # 2019, 1, 1
            disabled=False,
        )
        date_instr = HTML(value="<b>Pick a date:</b>", layout=Layout(padding="10px"))
        dates_box = HBox([self.start_date, self.end_date])
        dates_vbox = VBox([date_instr, dates_box])
        return dates_vbox

    def get_cloud_threshold_slider(self):
        instr = HTML(value="<b>Maximum percetange of cloud pixels allowed</b>")
        self.cloud_threshold_slider = ipywidgets.FloatSlider(
            value=0.5,
            min=0,
            max=1,
            step=0.01,
            description="Cloud Pixel %:",
            disabled=False,
            continuous_update=False,
            orientation="horizontal",
            readout=True,
            readout_format=".2f",
            style={"description_width": "initial"},
        )
        return VBox([instr, self.cloud_threshold_slider])

    def get_pansharpen_toggle(self):
        instr = HTML(value="<b>Switch pansharpening off for Landsat 7/8/9 imagery</b>")
        self.pansharpen_toggle = ipywidgets.ToggleButtons(
            options=["Pansharpen Off", "Pansharpen On"],
            description="",
            disabled=False,
            button_style="",
        )
        return VBox([instr, self.pansharpen_toggle])

    def get_sand_dropbox(self):
        sand_color_instr = HTML(
            value="<b>Sand color on beach for model to detect 'dark' (grey/black) 'bright' (white)</b>"
        )
        self.sand_dropdown = ipywidgets.Dropdown(
            options=["default", "latest", "dark", "bright"],
            value="default",
            description="Sand Color:",
            disabled=False,
        )
        return VBox([sand_color_instr, self.sand_dropdown])

    def get_alongshore_distance_slider(self):
        # returns slider to control beach area slider
        instr = HTML(
            value="<b>Along-shore distance over which to consider shoreline points to compute median intersection with transects</b>"
        )
        self.alongshore_distance_slider = ipywidgets.IntSlider(
            value=25,
            min=10,
            max=100,
            step=1,
            description="Alongshore Distance:",
            disabled=False,
            continuous_update=False,
            orientation="horizontal",
            readout=True,
            readout_format="d",
            style={"description_width": "initial"},
        )
        return VBox([instr, self.alongshore_distance_slider])

    def get_cloud_slider(self):
        # returns slider to control beach area slider
        cloud_instr = HTML(
            value="<b>Allowed distance from extracted shoreline to detected clouds</b>\
        </br>- Any extracted shorelines within this distance to any clouds will be dropped"
        )

        self.cloud_slider = ipywidgets.IntSlider(
            value=300,
            min=100,
            max=1000,
            step=1,
            description="Cloud Distance (m):",
            disabled=False,
            continuous_update=False,
            orientation="horizontal",
            readout=True,
            readout_format="d",
            style={"description_width": "initial"},
        )
        return VBox([cloud_instr, self.cloud_slider])

    def get_shoreline_buffer_slider(self):
        # returns slider to control beach area slider
        shoreline_buffer_instr = HTML(
            value="<b>Buffer around reference shorelines in which shorelines can be extracted</b>"
        )

        self.shoreline_buffer_slider = ipywidgets.IntSlider(
            value=50,
            min=100,
            max=500,
            step=1,
            description="Reference Shoreline Buffer (m):",
            disabled=False,
            continuous_update=False,
            orientation="horizontal",
            readout=True,
            readout_format="d",
            style={"description_width": "initial"},
        )
        return VBox([shoreline_buffer_instr, self.shoreline_buffer_slider])

    def get_beach_area_slider(self):
        # returns slider to control beach area slider
        beach_area_instr = HTML(
            value="<b>Minimum area (sqm) for object to be labelled as beach</b>"
        )

        self.beach_area_slider = ipywidgets.IntSlider(
            value=4500,
            min=1000,
            max=10000,
            step=10,
            description="Beach Area (sqm):",
            disabled=False,
            continuous_update=False,
            orientation="horizontal",
            readout=True,
            readout_format="d",
            style={"description_width": "initial"},
        )
        return VBox([beach_area_instr, self.beach_area_slider])

    def get_min_length_sl_slider(self):
        # returns slider to control beach area slider
        min_length_sl_instr = HTML(
            value="<b>Minimum shoreline perimeter that model will detect</b>"
        )

        self.min_length_sl_slider = ipywidgets.IntSlider(
            value=500,
            min=200,
            max=1000,
            step=1,
            description="Min shoreline length (m):",
            disabled=False,
            continuous_update=False,
            orientation="horizontal",
            readout=True,
            readout_format="d",
            style={"description_width": "initial"},
        )
        return VBox([min_length_sl_instr, self.min_length_sl_slider])

    def get_satellite_radio(self):
        # satellite selection widgets
        satellite_instr = HTML(
            value="<b>Pick multiple satellites:</b>\
                <br> - Pick multiple satellites by holding the control key> \
                <br> - images after 2022/01/01 will be automatically downloaded from Collection 2 ",
            layout=Layout(padding="10px"),
        )

        self.satellite_selection = SelectMultiple(
            options=["L5", "L7", "L8", "L9", "S2"],
            value=["L8"],
            description="Satellites",
            disabled=False,
        )
        satellite_vbox = VBox([satellite_instr, self.satellite_selection])
        return satellite_vbox

    def save_to_file_buttons(self):
        # save to file buttons
        save_instr = HTML(
            value="<h2>Save to file</h2>\
                Save feature on the map to a geojson file.\
                <br>Geojson file will be saved to CoastSeg directory.\
            ",
            layout=Layout(padding="0px"),
        )

        self.save_radio = RadioButtons(
            options=[
                "Shoreline",
                "Transects",
                "Bbox",
                "ROIs",
            ],
            value="Shoreline",
            description="",
            disabled=False,
        )

        self.save_button = Button(
            description=f"Save {self.save_radio.value}",
            icon="fa-floppy-o",
            style=self.save_style,
        )
        self.save_button.on_click(self.save_to_file_btn_clicked)

        def save_radio_changed(change):
            self.save_button.description = f"Save {str(change['new'])} to file"

        self.save_radio.observe(save_radio_changed, "value")
        save_vbox = VBox([save_instr, self.save_radio, self.save_button])
        return save_vbox

    def load_feature_on_map_buttons(self):
        load_instr = HTML(
            value="<h2>Load Feature into Bounding Box</h2>\
                Loads shoreline or transects into bounding box on map.\
                </br>If no transects or shorelines exist in this area, then\
               </br> draw bounding box somewhere else\
                ",
            layout=Layout(padding="0px"),
        )
        self.load_radio = RadioButtons(
            options=["Shoreline", "Transects"],
            value="Transects",
            description="",
            disabled=False,
        )
        self.load_button = Button(
            description=f"Load {self.load_radio.value}",
            icon="fa-file-o",
            style=self.load_style,
        )
        self.load_button.on_click(self.load_button_clicked)

        def handle_load_radio_change(change):
            self.load_button.description = f"Load {str(change['new'])}"

        self.load_radio.observe(handle_load_radio_change, "value")
        load_buttons = VBox([load_instr, self.load_radio, self.load_button])
        return load_buttons

    def remove_buttons(self):
        # define remove feature radio box button
        remove_instr = HTML(
            value="<h2>Remove Feature from Map</h2>",
            layout=Layout(padding="0px"),
        )

        self.remove_radio = RadioButtons(
            options=["Shoreline", "Transects", "Bbox", "ROIs"],
            value="Shoreline",
            description="",
            disabled=False,
        )
        self.remove_button = Button(
            description=f"Remove {self.remove_radio.value}",
            icon="fa-ban",
            style=self.remove_style,
        )

        def handle_remove_radio_change(change):
            self.remove_button.description = f"Remove {str(change['new'])}"

        self.remove_button.on_click(self.remove_feature_from_map)
        self.remove_radio.observe(handle_remove_radio_change, "value")
        # define remove all button
        self.remove_all_button = Button(
            description="Remove all", icon="fa-trash-o", style=self.remove_style
        )
        self.remove_all_button.on_click(self.remove_all_from_map)

        remove_buttons = VBox(
            [
                remove_instr,
                self.remove_radio,
                self.remove_button,
                self.remove_all_button,
            ]
        )
        return remove_buttons

    def get_settings_html(
        self,
        settings: dict,
    ):
        # if a key is missing from settings its value is "unknown"
        values = defaultdict(lambda: "unknown", settings)
        return """ 
        <h2>Settings</h2>
        <p>sat_list: {}</p>
        <p>dates: {}</p>
        <p>landsat_collection: {}</p>
        <p>cloud_thresh: {}</p>
        <p>dist_clouds: {}</p>
        <p>output_epsg: {}</p>
        <p>save_figure: {}</p>
        <p>min_beach_area: {}</p>
        <p>min_length_sl: {}</p>
        <p>cloud_mask_issue: {}</p>
        <p>sand_color: {}</p>
        <p>pan_off: {}</p>
        <p>max_dist_ref: {}</p>
        <p>along_dist: {}</p>
        """.format(
            values["sat_list"],
            values["dates"],
            values["landsat_collection"],
            values["cloud_thresh"],
            values["dist_clouds"],
            values["output_epsg"],
            values["save_figure"],
            values["min_beach_area"],
            values["min_length_sl"],
            values["cloud_mask_issue"],
            values["sand_color"],
            values["pan_off"],
            values["max_dist_ref"],
            values["along_dist"],
        )

    def _create_HTML_widgets(self):
        """create HTML widgets that display the instructions.
        widgets created: instr_create_ro, instr_save_roi, instr_load_btns
         instr_download_roi
        """
        self.instr_create_roi = HTML(
            value="<h2><b>Generate ROIs on Map</b></h2> \
                </br><b>No Overlap</b>: Set Small ROI Area to 0 and Large ROI Area to ROI area.</li>\
                </br><b>Overlap</b>: Set Small ROI Area to a value and Large ROI Area to ROI area.</li>\
                </br><h3><b><u>How ROIs are Made</u></b></br></h3> \
                <li>Two grids of ROIs (squares) are created within\
                </br>the bounding box along the shoreline.\
                <li>If no shoreline is within the bounding box then ROIs cannot be created.\
                ",
            layout=Layout(margin="0px 5px 0px 0px"),
        )

        self.instr_download_roi = HTML(
            value="<h2><b>Download Imagery</b></h2> \
                <li><b>You must click an ROI on the map before you can download ROIs</b> \
                <li>Scroll past the map to see the download progress \
                </br><h3><b><u>Where is my data?</u></b></br></h3> \
                <li>The data you downloaded will be in the 'data' folder in the main CoastSeg directory</li>\
                Each ROI you downloaded will have its own folder with the ROI's ID and\
                </br>the time it was downloaded in the folder name\
                </br><b>Example</b>: 'ID_1_datetime11-03-22__02_33_22'</li>\
                ",
            layout=Layout(margin="0px 0px 0px 5px"),
        )

        self.instr_config_btns = HTML(
            value="<h2><b>Load and Save Config Files</b></h2>\
                <b>Load Config</b>: Load rois, shorelines, transects and bounding box from file: 'config_gdf.geojson'\
                <li>'config.json' must be in the same directory as 'config_gdf.geojson'.</li>\
                <b>Save Config</b>: Saves rois, shorelines, transects and bounding box to file: 'config_gdf.geojson'\
                </br><b>ROIs Not Downloaded:</b> config file will be saved to CoastSeg directory in file: 'config_gdf.geojson'\
                </br><b>ROIs Not Downloaded:</b>config file will be saved to each ROI's directory in file: 'config_gdf.geojson'\
                ",
            layout=Layout(margin="0px 5px 0px 5px"),
        )  # top right bottom left

    def create_dashboard(self):
        """creates a dashboard containing all the buttons, instructions and widgets organized together."""
        # create settings section
        settings_section = self.get_settings_section()
        # Buttons to load shoreline or transects in bbox on map
        load_buttons = self.load_feature_on_map_buttons()
        remove_buttons = self.remove_buttons()
        save_to_file_buttons = self.save_to_file_buttons()

        load_file_vbox = VBox(
            [self.load_file_instr, self.load_file_radio, self.load_file_button]
        )
        save_vbox = VBox(
            [
                save_to_file_buttons,
                load_file_vbox,
                remove_buttons,
            ]
        )
        config_vbox = VBox(
            [self.instr_config_btns, self.load_configs_button, self.save_config_button]
        )
        download_vbox = VBox(
            [
                self.instr_download_roi,
                self.download_button,
                self.extract_shorelines_button,
                self.compute_transect_button,
                self.save_transect_csv_button,
                config_vbox,
            ]
        )

        area_control_box = VBox(
            [
                self.roi_slider_instr,
                self.units_radio,
                self.sm_area_textbox,
                self.lg_area_textbox,
            ]
        )
        ROI_btns_box = VBox([area_control_box, self.gen_button])
        roi_controls_box = VBox(
            [self.instr_create_roi, ROI_btns_box, load_buttons],
            layout=Layout(margin="0px 5px 5px 0px"),
        )

        # view currently loaded settings
        static_settings_html = self.get_view_settings_vbox()

        settings_row = HBox([settings_section, static_settings_html])
        row_1 = HBox([roi_controls_box, save_vbox, download_vbox])
        # in this row prints are rendered with UI.debug_view
        row_2 = HBox([self.clear_debug_button, UI.debug_view])
        self.error_row = HBox([])
        self.file_chooser_row = HBox([])
        map_row = HBox([self.coastseg_map.map])
        download_msgs_row = HBox([UI.download_view])

        return display(
            settings_row,
            row_1,
            row_2,
            self.error_row,
            self.file_chooser_row,
            map_row,
            download_msgs_row,
        )

    @debug_view.capture(clear_output=True)
    def update_settings_btn_clicked(self, btn):
        UI.debug_view.clear_output(wait=True)
        # Update settings in view settings section
        try:
            self.settings_html.value = self.get_settings_html(
                self.coastseg_map.settings
            )
        except Exception as error:
            exception_handler.handle_exception(error, self.coastseg_map.warning_box)

    @debug_view.capture(clear_output=True)
    def gen_roi_clicked(self, btn):
        UI.debug_view.clear_output(wait=True)
        self.coastseg_map.map.default_style = {"cursor": "wait"}
        self.gen_button.disabled = True
        # Generate ROIs along the coastline within the bounding box
        try:
            print("Generating ROIs please wait...")
            self.coastseg_map.load_feature_on_map(
                "rois",
                lg_area=self.lg_area_textbox.value,
                sm_area=self.sm_area_textbox.value,
                units=self.units_radio.value,
            )
        except Exception as error:
            print("ROIs could not be generated")
            self.coastseg_map.map.default_style = {"cursor": "default"}
            exception_handler.handle_exception(error, self.coastseg_map.warning_box)
        else:
            self.coastseg_map.map.default_style = {"cursor": "default"}
            print("ROIs generated. Please Select at least one ROI and click Save ROI.")
        self.coastseg_map.map.default_style = {"cursor": "default"}
        self.gen_button.disabled = False

    @debug_view.capture(clear_output=True)
    def load_button_clicked(self, btn):
        UI.debug_view.clear_output(wait=True)
        self.coastseg_map.map.default_style = {"cursor": "wait"}
        try:
            if "shoreline" in btn.description.lower():
                print("Finding Shoreline")
                self.coastseg_map.load_feature_on_map("shoreline")
            if "transects" in btn.description.lower():
                print("Finding 'Transects'")
                self.coastseg_map.load_feature_on_map("transects")
        except Exception as error:
            # renders error message as a box on map
            exception_handler.handle_exception(error, self.coastseg_map.warning_box)
        self.coastseg_map.map.default_style = {"cursor": "default"}

    @debug_view.capture(clear_output=True)
    def save_settings_clicked(self, btn):
        if self.satellite_selection.value:
            # Save satellites selected by user
            sat_list = list(self.satellite_selection.value)
            # Save dates selected by user
            dates = [str(self.start_date.value), str(self.end_date.value)]
            output_epsg = int(self.output_epsg_text.value)
            max_dist_ref = self.shoreline_buffer_slider.value
            along_dist = self.alongshore_distance_slider.value
            dist_clouds = self.cloud_slider.value
            beach_area = self.beach_area_slider.value
            min_length_sl = self.min_length_sl_slider.value
            sand_color = str(self.sand_dropdown.value)
            pansharpen_enabled = (
                False if "off" in self.pansharpen_toggle.value.lower() else True
            )
            cloud_thresh = self.cloud_threshold_slider.value
            settings = {
                "sat_list": sat_list,
                "dates": dates,
                "output_epsg": output_epsg,
                "max_dist_ref": max_dist_ref,
                "along_dist": along_dist,
                "dist_clouds": dist_clouds,
                "min_beach_area": beach_area,
                "min_length_sl": min_length_sl,
                "sand_color": sand_color,
                "pan_off": pansharpen_enabled,
                "cloud_thresh": cloud_thresh,
            }
            try:
                self.coastseg_map.save_settings(**settings)
                self.settings_html.value = self.get_settings_html(
                    self.coastseg_map.settings
                )
            except Exception as error:
                # renders error message as a box on map
                exception_handler.handle_exception(error, self.coastseg_map.warning_box)
        elif not self.satellite_selection.value:
            try:
                raise Exception("Must select at least one satellite first")
            except Exception as error:
                # renders error message as a box on map
                exception_handler.handle_exception(error, self.coastseg_map.warning_box)

    @debug_view.capture(clear_output=True)
    def extract_shorelines_button_clicked(self, btn):
        UI.debug_view.clear_output()
        self.coastseg_map.map.default_style = {"cursor": "wait"}
        self.extract_shorelines_button.disabled = True
        try:
            self.coastseg_map.extract_all_shorelines()
        except Exception as error:
            # renders error message as a box on map
            exception_handler.handle_exception(error, self.coastseg_map.warning_box)
        self.extract_shorelines_button.disabled = False
        self.coastseg_map.map.default_style = {"cursor": "default"}

    @debug_view.capture(clear_output=True)
    def compute_transect_button_clicked(self, btn):
        UI.debug_view.clear_output()
        self.coastseg_map.map.default_style = {"cursor": "wait"}
        self.compute_transect_button.disabled = True
        try:
            self.coastseg_map.compute_transects()
        except Exception as error:
            # renders error message as a box on map
            exception_handler.handle_exception(error, self.coastseg_map.warning_box)
        self.compute_transect_button.disabled = False
        self.coastseg_map.map.default_style = {"cursor": "default"}

    @download_view.capture(clear_output=True)
    def download_button_clicked(self, btn):
        UI.download_view.clear_output()
        UI.debug_view.clear_output()
        self.coastseg_map.map.default_style = {"cursor": "wait"}
        self.download_button.disabled = True
        UI.debug_view.append_stdout("Scroll down past map to see download progress.")
        try:
            try:
                self.download_button.disabled = True
                self.coastseg_map.download_imagery()
            except Exception as error:
                # renders error message as a box on map
                exception_handler.handle_exception(error, self.coastseg_map.warning_box)
        except google_auth_exceptions.RefreshError as exception:
            print(exception)
            exception_handler.handle_exception(
                exception,
                self.coastseg_map.warning_box,
                title="Authentication Error",
                msg="Please authenticate with Google using the cell above: \n Authenticate and Initialize with Google Earth Engine (GEE)",
            )
        self.download_button.disabled = False
        self.coastseg_map.map.default_style = {"cursor": "default"}

    @debug_view.capture(clear_output=True)
    def on_save_cross_distances_button_clicked(self, btn):
        UI.debug_view.clear_output(wait=True)
        try:
            self.coastseg_map.save_transects_to_csv()
        except Exception as error:
            # renders error message as a box on map
            exception_handler.handle_exception(error, self.coastseg_map.warning_box)

    def clear_row(self, row: HBox):
        """close widgets in row/column and clear all children
        Args:
            row (HBox)(VBox): row or column
        """
        for index in range(len(row.children)):
            row.children[index].close()
        row.children = []

    @debug_view.capture(clear_output=True)
    def on_load_configs_clicked(self, button):
        # Prompt user to select a config geojson file
        def load_callback(filechooser: FileChooser) -> None:
            try:
                if filechooser.selected:
                    self.coastseg_map.load_configs(filechooser.selected)
                    self.settings_html.value = self.get_settings_html(
                        self.coastseg_map.settings
                    )
            except Exception as error:
                # renders error message as a box on map
                exception_handler.handle_exception(error, self.coastseg_map.warning_box)

        # create instance of chooser that calls load_callback
        file_chooser = create_file_chooser(load_callback)
        # clear row and close all widgets in row_4 before adding new file_chooser
        self.clear_row(self.file_chooser_row)
        # add instance of file_chooser to row 4
        self.file_chooser_row.children = [file_chooser]

    @debug_view.capture(clear_output=True)
    def on_save_config_clicked(self, button):
        try:
            self.coastseg_map.save_config()
        except Exception as error:
            # renders error message as a box on map
            exception_handler.handle_exception(error, self.coastseg_map.warning_box)

    @debug_view.capture(clear_output=True)
    def load_feature_from_file(self, btn):
        # Prompt user to select a geojson file
        def load_callback(filechooser: FileChooser) -> None:
            try:
                if filechooser.selected:
                    if "shoreline" in btn.description.lower():
                        print(
                            f"Loading shoreline from file: {os.path.abspath(filechooser.selected)}"
                        )
                        self.coastseg_map.load_feature_on_map(
                            "shoreline", os.path.abspath(filechooser.selected)
                        )
                    if "transects" in btn.description.lower():
                        print(
                            f"Loading transects from file: {os.path.abspath(filechooser.selected)}"
                        )
                        self.coastseg_map.load_feature_on_map(
                            "transects", os.path.abspath(filechooser.selected)
                        )
                    if "bbox" in btn.description.lower():
                        print(
                            f"Loading bounding box from file: {os.path.abspath(filechooser.selected)}"
                        )
                        self.coastseg_map.load_feature_on_map(
                            "bbox", os.path.abspath(filechooser.selected)
                        )
                    if "rois" in btn.description.lower():
                        print(
                            f"Loading ROIs from file: {os.path.abspath(filechooser.selected)}"
                        )
                        self.coastseg_map.load_feature_on_map(
                            "rois", os.path.abspath(filechooser.selected)
                        )
            except Exception as error:
                # renders error message as a box on map
                exception_handler.handle_exception(error, self.coastseg_map.warning_box)

        # change title of filechooser based on feature selected
        title = "Select a geojson file"
        # create instance of chooser that calls load_callback
        if "shoreline" in btn.description.lower():
            title = "Select shoreline geojson file"
        if "transects" in btn.description.lower():
            title = "Select transects geojson file"
        if "bbox" in btn.description.lower():
            title = "Select bounding box geojson file"
        if "rois" in btn.description.lower():
            title = "Select ROI geojson file"
        # create instance of chooser that calls load_callback
        file_chooser = create_file_chooser(load_callback, title=title)
        # clear row and close all widgets in row_4 before adding new file_chooser
        self.clear_row(self.file_chooser_row)
        # add instance of file_chooser to row 4
        self.file_chooser_row.children = [file_chooser]

    @debug_view.capture(clear_output=True)
    def remove_feature_from_map(self, btn):
        UI.debug_view.clear_output(wait=True)
        try:
            # Prompt the user to select a directory of images
            if "shoreline" in btn.description.lower():
                print(f"Removing shoreline")
                self.coastseg_map.remove_shoreline()
            if "transects" in btn.description.lower():
                print(f"Removing  transects")
                self.coastseg_map.remove_transects()
            if "bbox" in btn.description.lower():
                print(f"Removing bounding box")
                self.coastseg_map.remove_bbox()
            if "rois" in btn.description.lower():
                print(f"Removing ROIs")
                self.coastseg_map.remove_all_rois()
        except Exception as error:
            # renders error message as a box on map
            exception_handler.handle_exception(error, self.coastseg_map.warning_box)

    @debug_view.capture(clear_output=True)
    def save_to_file_btn_clicked(self, btn):
        UI.debug_view.clear_output(wait=True)
        try:
            if "shoreline" in btn.description.lower():
                print(f"Saving shoreline to file")
                self.coastseg_map.save_feature_to_file(
                    self.coastseg_map.shoreline, "shoreline"
                )
            if "transects" in btn.description.lower():
                print(f"Saving transects to file")
                self.coastseg_map.save_feature_to_file(
                    self.coastseg_map.transects, "transects"
                )
            if "bbox" in btn.description.lower():
                print(f"Saving bounding box to file")
                self.coastseg_map.save_feature_to_file(
                    self.coastseg_map.bbox, "bounding box"
                )
            if "rois" in btn.description.lower():
                print(f"Saving ROIs to file")
                self.coastseg_map.save_feature_to_file(self.coastseg_map.rois, "ROI")
        except Exception as error:
            # renders error message as a box on map
            exception_handler.handle_exception(error, self.coastseg_map.warning_box)

    @debug_view.capture(clear_output=True)
    def remove_all_from_map(self, btn):
        try:
            self.coastseg_map.remove_all()
        except Exception as error:
            # renders error message as a box on map
            exception_handler.handle_exception(error, self.coastseg_map.warning_box)

    def clear_debug_view(self, btn):
        UI.debug_view.clear_output()
        UI.download_view.clear_output()
