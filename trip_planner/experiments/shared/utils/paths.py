"""Locations of the experiment data, anchored to this file."""

import pathlib

EXPERIMENTS = pathlib.Path(__file__).resolve().parents[2]
DATA = EXPERIMENTS / 'data'

PICOS_TRAILS = DATA / 'picos_trails'
HIKING_GEAR = DATA / 'hiking_gear'
