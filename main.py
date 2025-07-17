import osmnx as ox
import networkx as nx
import pygame
import sys
import random
import pickle
import os
import requests

# Config
WIDTH, HEIGHT = 700, 700
NODE_RADIUS = 1
CAR_COLOR = (255, 255, 0)
ROAD_COLOR = (50, 50, 50)
BG_COLOR = (240, 240, 240)
FPS = 60
MOVE_SPEED = 10  # node-to-node

# Get road network from Coimbatore
place = "Coimbatore, India"
graph_file = "coimbatore_graph.pkl"

if os.path.exists(graph_file):
    with open(graph_file, "rb") as f:
        G = pickle.load(f)
else:
    G = ox.graph_from_place(place, network_type='drive')
    with open(graph_file, "wb") as f:
        pickle.dump(G, f)

# Convert nodes to lat/lon DataFrame
nodes, edges = ox.graph_to_gdfs(G)

# 1. Calculate bounding box for the path
# Get user input for start and end location
def get_coordinates(prompt):
    while True:
        try:
            lat = float(input(f"{prompt} Latitude: "))
            lon = float(input(f"{prompt} Longitude: "))
            return lat, lon
        except ValueError:
            print("Invalid input. Please enter valid numbers.")

print("🔰 Enter starting point coordinates:")
start_lat, start_lon = get_coordinates("Start")

print("🏁 Enter ending point coordinates:")
end_lat, end_lon = get_coordinates("End")

# Convert coordinates to nearest OSM nodes
start_node = ox.distance.nearest_nodes(G, X=start_lon, Y=start_lat)
end_node = ox.distance.nearest_nodes(G, X=end_lon, Y=end_lat)

# Compute shortest path
try:
    path = nx.shortest_path(G, start_node, end_node, weight='length')
except nx.NetworkXNoPath:
    print("❌ No path found between the selected points.")
    sys.exit()


path_nodes = [G.nodes[n] for n in path]
minx = min(node['x'] for node in path_nodes)
maxx = max(node['x'] for node in path_nodes)
miny = min(node['y'] for node in path_nodes)
maxy = max(node['y'] for node in path_nodes)

def scale(x, y):
    # Use only the path bounding box for scaling
    sx = int((x - minx) / (maxx - minx) * WIDTH)
    sy = int((maxy - y) / (maxy - miny) * HEIGHT)  # invert y for pygame
    return sx, sy

# Only keep node positions within the bounding box
node_positions = {}
for node, data in G.nodes(data=True):
    if minx <= data['x'] <= maxx and miny <= data['y'] <= maxy:
        node_positions[node] = scale(data['x'], data['y'])

# Do NOT re-select start/end or path here!
# Use the original start_node, end_node, and path

# Pygame setup
pygame.init()
screen = pygame.display.set_mode((WIDTH, HEIGHT))
pygame.display.set_caption("🚗 Drive Coimbatore Roads")
clock = pygame.time.Clock()
font = pygame.font.SysFont("Arial", 24)

current_index = 0  # index in path

def draw_map():
    screen.fill(BG_COLOR)
    # Draw edges (roads) only within bounding box
    for u, v in G.edges():
        if u in node_positions and v in node_positions:
            pygame.draw.line(screen, ROAD_COLOR, node_positions[u], node_positions[v], 2)

    # Draw nodes within bounding box
    for node, (x, y) in node_positions.items():
        pygame.draw.circle(screen, (100, 100, 255), (x, y), NODE_RADIUS)

    # Draw path
    for i in range(len(path) - 1):
        pygame.draw.line(screen, (255, 0, 0), node_positions[path[i]], node_positions[path[i+1]], 4)

    # Draw car
    car_x, car_y = node_positions[path[current_index]]
    pygame.draw.circle(screen, CAR_COLOR, (car_x, car_y), NODE_RADIUS + 3)

    # Draw start/end
    pygame.draw.circle(screen, (0, 255, 0), node_positions[start_node], NODE_RADIUS + 5)
    pygame.draw.circle(screen, (255, 0, 0), node_positions[end_node], NODE_RADIUS + 5)

    # Show current location (lat/lon, name, road, address)
    car_node = path[current_index]
    car_data = G.nodes[car_node]
    location_text = f"Lat: {car_data['y']:.5f}, Lon: {car_data['x']:.5f}"

    node_name = car_data.get('name', '')
    if node_name:
        location_text += f" | Location: {node_name}"

    road_name = ""
    if current_index < len(path) - 1:
        edge_data = G.get_edge_data(path[current_index], path[current_index + 1])
        if edge_data:
            edge_info = list(edge_data.values())[0]
            road_name = edge_info.get('name', '')
    if road_name:
        location_text += f" | Road: {road_name}"

    location_name = reverse_geocode(car_data['y'], car_data['x'])
    location_text += f" | Address: {location_name}"

    loc_msg = font.render(location_text, True, (0, 0, 0))
    screen.blit(loc_msg, (10, HEIGHT - 60))

    # Show end location (lat/lon, name, address)
    end_data = G.nodes[end_node]
    end_text = f"Destination: Lat: {end_data['y']:.5f}, Lon: {end_data['x']:.5f}"

    end_name = end_data.get('name', '')
    if end_name:
        end_text += f" | Location: {end_name}"

    end_address = reverse_geocode(end_data['y'], end_data['x'])
    end_text += f" | Address: {end_address}"

    end_msg = font.render(end_text, True, (0, 0, 0))
    screen.blit(end_msg, (10, HEIGHT - 30))

def show_message(text):
    msg = font.render(text, True, (0, 0, 0))
    screen.blit(msg, (WIDTH // 2 - msg.get_width() // 2, HEIGHT - 40))

def reverse_geocode(lat, lon):
    url = f"https://nominatim.openstreetmap.org/reverse"
    params = {
        'lat': lat,
        'lon': lon,
        'format': 'json',
        'zoom': 18,
        'addressdetails': 1
    }
    headers = {'User-Agent': 'YourAppName'}
    response = requests.get(url, params=params, headers=headers)
    if response.status_code == 200:
        data = response.json()
        return data.get('display_name', 'Unknown location')
    return 'Unknown location'

# Game loop
running = True
while running:
    clock.tick(FPS)
    screen.fill((0, 0, 0))
    draw_map()

    for event in pygame.event.get():
        if event.type == pygame.QUIT:
            running = False

    # Key press to move along path
    keys = pygame.key.get_pressed()
    if keys[pygame.K_RIGHT] and current_index < len(path) - 1:
        current_index += 1
        pygame.time.delay(150)
    if keys[pygame.K_LEFT] and current_index > 0:
        current_index -= 1
        pygame.time.delay(150)

    if current_index == len(path) - 1:
        show_message("🎉 Reached Destination!")

    pygame.display.flip()

pygame.quit()
sys.exit()
