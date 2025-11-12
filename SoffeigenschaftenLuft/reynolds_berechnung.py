import numpy as np

def berechne_kinematische_viskositaet(dynamic_viscosity, density):
    """
    Berechnet die kinematische Viskosität aus der dynamischen Viskosität und der Dichte.
    
    :param dynamic_viscosity: Dynamische Viskosität in Pa·s (kg/(m·s))
    :param density: Dichte des Mediums in kg/m³
    :return: Kinematische Viskosität in m²/s
    """
    if density <= 0:
        raise ValueError("Die Dichte muss größer als 0 sein.")
    
    return dynamic_viscosity / density

def berechne_reynolds(diameter, velocity, dynamic_viscosity, density):
    """
    Berechnet die Reynolds-Zahl für eine Rohrströmung.
    
    :param diameter: Rohrdurchmesser in m
    :param velocity: Strömungsgeschwindigkeit in m/s
    :param dynamic_viscosity: Dynamische Viskosität in Pa·s (kg/(m·s))
    :param density: Dichte des Mediums in kg/m³
    :return: Reynolds-Zahl (dimensionslos)
    """
    kinematic_viscosity = berechne_kinematische_viskositaet(dynamic_viscosity, density)
    
    if kinematic_viscosity <= 0:
        raise ValueError("Die kinematische Viskosität muss größer als 0 sein.")
    
    reynolds = (diameter * velocity) / kinematic_viscosity
    return reynolds