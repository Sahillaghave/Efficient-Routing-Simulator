# Efficient Routing in Computer Networks

An interactive web-based simulation of efficient routing in computer networks using Python and Dijkstra's Shortest Path Algorithm.

## 📌 Project Overview

Efficient routing is an important concept in computer networks. It helps select a suitable path for transferring data from a source router to a destination router.

This project simulates a computer network in which routers are represented as nodes and connections between routers are represented as weighted edges. Dijkstra's algorithm calculates the minimum-cost path between the selected source and destination.

The application provides an interactive dashboard to visualize network topology, modify link costs, simulate link failures, and observe how routing decisions change.

## 🎯 Objectives

- Understand the concept of efficient routing.
- Implement Dijkstra's shortest-path algorithm using Python.
- Visualize routers and network connections.
- Calculate minimum-cost paths between routers.
- Observe how link-cost changes affect routing decisions.
- Simulate network link failures and alternative routes.
- Understand basic routing metrics through an interactive demonstration.

## ✨ Features

- **Interactive Network Visualization:** View routers and weighted network links.
- **Shortest-Path Calculation:** Calculate the minimum-cost route using Dijkstra's algorithm.
- **Source and Destination Selection:** Choose routers for route calculation.
- **Link Cost Modification:** Change connection costs and recalculate routes.
- **Link Failure Simulation:** Disable network links and observe alternative paths.
- **Step-by-Step Execution:** Understand the algorithm's routing decisions.
- **Performance Metrics:** View route cost, hop count, and network information.
- **Interactive Dashboard:** Explore routing concepts through a web interface.

## 🛠️ Technologies Used

- Python
- Streamlit
- NetworkX
- Plotly
- Dijkstra's Shortest Path Algorithm

## 🗺️ Network Representation

The simulated network contains six routers:

`A, B, C, D, E, F`

Each router represents a node, and each connection represents an edge with an associated cost.

The initial network connections are:

| Connection | Cost |
|---|---:|
| A – B | 4 |
| A – C | 2 |
| B – C | 1 |
| B – D | 5 |
| C – D | 8 |
| C – E | 10 |
| D – E | 2 |
| D – F | 6 |
| E – F | 3 |
| B – E | 7 |

These costs are configurable values used by the simulation.

## ⚙️ Installation and Setup

### Prerequisites

- Python 3.10 or a compatible version supported by the installed dependencies
- Git
- A web browser

### Step 1: Clone the repository

```bash
git clone https://github.com/YOUR-USERNAME/efficient-routing-simulator.git
```

Replace `YOUR-USERNAME` with your GitHub username.

### Step 2: Open the project folder

```bash
cd efficient-routing-simulator
```

### Step 3: Install dependencies

```bash
python -m pip install -r requirements.txt
```

### Step 4: Run the application

```bash
python -m streamlit run app.py
```

The application will open in your browser. If it does not open automatically, use the local URL displayed in the terminal, usually `http://localhost:8501`.

## 🧪 How to Use

1. Open the routing simulator.
2. Explore the network topology and link costs.
3. Select a source router and destination router.
4. Run the routing simulation.
5. Observe the calculated shortest path and total cost.
6. Modify a link cost and run the simulation again.
7. Disable a link to simulate a connection failure.
8. Observe whether an alternative route exists.
9. Explore the algorithm steps and displayed network metrics.

## 🧠 Algorithm Used

Dijkstra's algorithm calculates shortest paths from a source node in a graph with non-negative edge weights.

The algorithm repeatedly selects the reachable node with the smallest tentative distance and updates the distances of its neighboring nodes whenever a lower-cost path is found.

The final result is the minimum-cost path to the selected destination, if that destination is reachable.

## 📊 Expected Outcomes

- Visualization of a weighted computer network.
- Calculation of minimum-cost routes.
- Understanding of how link costs affect routing decisions.
- Demonstration of alternative routing paths after a simulated link failure.
- Better understanding of graph-based routing algorithms.

## ⚠️ Project Scope and Limitations

This project is a software-based educational simulation. It does not connect to physical routers or measure live network traffic.

Link costs are configurable simulation values and do not automatically represent actual bandwidth, delay, congestion, or packet loss.

## 🎓 Academic Information

**Project:** Efficient Routing in Computer Networks  
**Activity:** CIA Part-B  
**Department:** Computer Engineering  
**Academic Year:** 2026–27  
**Institution:** Sanjivani College of Engineering

## 👥 Team Members

- Sahil Laghave
- Om Dhanapune
- Rohit Somase
- Yogesh Dane

## 📚 References

- James F. Kurose and Keith W. Ross — *Computer Networking: A Top-Down Approach*
- Andrew S. Tanenbaum — *Computer Networks*
- RFC 2328 — OSPF Version 2
- RFC 4271 — Border Gateway Protocol 4 (BGP-4)
- Cisco Networking Academy Documentation

---

**Note:** This project is developed for educational purposes to demonstrate routing concepts and shortest-path calculations.