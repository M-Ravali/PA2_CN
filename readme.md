# BitTorrent Simulator

## Overview
This is an event-driven BitTorrent simulator that models a peer-to-peer network with seeds, leechers, and a tracker. The simulator implements the core BitTorrent protocol along with key algorithms like Local Rarest First (LRF) for piece selection and Tit-for-Tat with optimistic unchoking for peer selection.

## Project Structure
- `main.py`: Main BitTorrent simulator with working piece transfer
- `parse_logs.py`: Script to analyze simulation logs and generate statistics
- `graphs.py`: Script to generate visualization graphs
- `report.md`: Detailed report on the simulator and analysis results
- `paste.txt`: Sample simulation output log
- `graphs/`: Directory containing generated graphs and CSV data

## Dependencies
- Python 3.6+
- matplotlib
- numpy

## Installation
1. Download the folder.
2. Install dependencies:
```
pip install matplotlib numpy
```

## Running the Simulator
To run the BitTorrent simulator:
```
python main.py
```
This will run the simulation and save the output to `paste.txt`.

## Generating Graphs
To generate analysis graphs from the simulation data:
```
python graphs.py
```
This will create three graphs in the `graphs/` directory:
1. File completion time vs. number of peers
2. Number of active peers over time
3. File completion time vs. download/upload speed

## Analyzing Logs
To analyze the simulation logs and generate CSV files with statistics:
```
python parse_logs.py
```
This will create several CSV files in the `log_analysis/` directory:
1. `piece_transfers.csv`: Record of all piece transfers
2. `peer_progress.csv`: Progress of each leecher over time
3. `choke_events.csv`: Record of choking/unchoking events
4. `interest_events.csv`: Record of interest expressions

## Implemented Features
- Event-driven simulation architecture
- BitTorrent protocol message flows (handshake, bitfield, interested, choke, etc.)
- Local Rarest First (LRF) piece selection algorithm
- Tit-for-Tat with optimistic unchoking peer selection algorithm
- Piece rarity tracking and updates
- Choking/unchoking mechanism
- Interest expression based on available pieces

## Simulation Parameters
You can adjust the following parameters in the `main.py` file:
- `num_seeds`: Number of seed peers (default: 1)
- `num_leechers`: Number of leecher peers (default: 5)
- `num_pieces`: Number of pieces in the file (default: 10)
- `max_time`: Maximum simulation time (default: 100)