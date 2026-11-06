"""All assumptions in one place. Each one is written up in METHOD.md."""
# Robot pick envelope: an editable assumption, NOT any vendor's specification.
ENVELOPE = dict(max_l=60.0, max_m=45.0, max_s=35.0, min_s=0.0)
CELL_RATE_H = 500.0          # sorts per hour per cell (published vendor configurator figure)
SERVICE_CV = 0.25            # coefficient of variation of per-pick time
MANUAL_RATE_H = 287.5        # parcels per hour per manual sorter (published range 275-300, midpoint)
WAGE_H = 18.10               # BLS OEWS May 2023 national median, SOC 53-7062
PEAK_UPLIFT = 0.10           # peak-season volume uplift over last year
# Inbound shape (SYNTHETIC ASSUMPTION: the dataset has no inbound scans)
INBOUND_OPEN_H = 3.0         # a route's parcels start arriving 3 h before its departure
INBOUND_CLOSE_H = 1.0        # ... and finish arriving 1 h before departure
CUTOFF_H = 0.5               # sorted parcels must be in the gaylord 30 min before departure
MISS_TARGET = 0.01           # size to < 1% of parcels late
GAYLORDS_PER_CELL = 8        # destinations a cell can hold (configurator range 6-16+)
UTC_OFFSET_H = {"DLA": -7, "DSE": -7, "DBO": -4, "DCH": -5, "DAU": -5}  # summer 2018 local time
# Business case (labelled assumptions; no vendor price is used anywhere)
OPS_PER_CELL = (0.5, 1, 2)   # robot-side operators per cell (0.5 = one operator tending two cells)
DAYS_PER_YEAR = 300          # sort days per year (6-day week less holidays)
# Bootstrap / replication counts
N_BOOT = 2000                # day-block resamples for intervals on packages/route and P90 routes
N_BOOT_DAYS = 200            # bootstrap design days run through the DES
REPS_LADDER = 20             # replications per cell count for the bound / EDF / FIFO ladder
