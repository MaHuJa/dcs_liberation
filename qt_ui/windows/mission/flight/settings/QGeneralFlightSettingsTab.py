from PySide2.QtCore import Signal
from PySide2.QtWidgets import QFrame, QGridLayout, QVBoxLayout, QLabel

from game import Game
from gen.ato import Package
from gen.flights.flight import Flight
from qt_ui.windows.mission.flight.settings.QFlightDepartureDisplay import \
    QFlightDepartureDisplay
from qt_ui.windows.mission.flight.settings.QFlightSlotEditor import \
    QFlightSlotEditor
from qt_ui.windows.mission.flight.settings.QFlightStartType import \
    QFlightStartType
from qt_ui.windows.mission.flight.settings.QFlightTypeTaskInfo import \
    QFlightTypeTaskInfo
from qt_ui.windows.mission.flight.settings.QCustomName import \
    QFlightCustomName


class QGeneralFlightSettingsTab(QFrame):
    on_flight_settings_changed = Signal()

    def __init__(self, game: Game, package: Package, flight: Flight):
        super().__init__()

        layout = QGridLayout()
        flight_info = QFlightTypeTaskInfo(flight)
        flight_departure = QFlightDepartureDisplay(package, flight)
        flight_slots = QFlightSlotEditor(flight, game)
        flight_start_type = QFlightStartType(flight)
        flight_custom_name = QFlightCustomName(flight)
        layout.addWidget(flight_info, 0, 0)
        layout.addWidget(flight_departure, 1, 0)
        layout.addWidget(flight_slots, 2, 0)
        layout.addWidget(flight_start_type, 3, 0)
        layout.addWidget(flight_custom_name, 4, 0)
        vstretch = QVBoxLayout()
        vstretch.addStretch()
        layout.addLayout(vstretch, 3, 0)
        self.setLayout(layout)

        flight_start_type.setEnabled(flight.client_count > 0)
        flight_slots.changed.connect(
            lambda: flight_start_type.setEnabled(flight.client_count > 0))
