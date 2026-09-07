import osmnx as ox
import networkx as nx
import random
import json
import os

def build_routing_for_place(place_name, place_tag, shelter_points):
    print(f"\n{'='*50}")
    print(f"Building routing pipeline for: {place_name}")
    print(f"{'='*50}")

    graphml_path = f"{place_tag}_roads.graphml"
    if os.path.exists(graphml_path):
        print("Road network already downloaded, loading from disk...")
        G = ox.load_graphml(graphml_path)
    else:
        print("Downloading road network (this may take a few minutes)...")
        G = ox.graph_from_place(place_name, network_type='drive')
        ox.save_graphml(G, filepath=graphml_path)

    G = ox.add_edge_speeds(G)
    G = ox.add_edge_travel_times(G)

    # Keep only the largest connected part of the road network
    largest_component = max(nx.weakly_connected_components(G), key=len)
    G = G.subgraph(largest_component).copy()

    random.seed(42)
    def risk_multiplier(flood_risk):
        return 1 + (flood_risk ** 2) * 19

    for u, v, k, data in G.edges(keys=True, data=True):
        base_time = data.get('travel_time', 60)
        if isinstance(base_time, list):
            base_time = base_time[0]
        flood_risk = round(random.uniform(0, 1), 2)
        data['flood_risk'] = flood_risk
        data['risk_weighted_time'] = base_time * risk_multiplier(flood_risk)

    nodes = list(G.nodes)
    random.seed(1)
    orig = random.choice(nodes)
    dest = random.choice(nodes)

    def get_route_stats(route):
        total_dist = total_time = total_risk = 0
        for i in range(len(route) - 1):
            edge = list(G.get_edge_data(route[i], route[i+1]).values())[0]
            total_dist += edge.get('length', 0)
            total_time += edge.get('travel_time', 0)
            total_risk += edge.get('risk_weighted_time', 0)
        return total_dist, total_time, total_risk

    fastest_route = nx.shortest_path(G, orig, dest, weight='travel_time')
    safest_route = nx.shortest_path(G, orig, dest, weight='risk_weighted_time')
    f_dist, f_time, f_risk = get_route_stats(fastest_route)
    s_dist, s_time, s_risk = get_route_stats(safest_route)

    shelter_nodes = {name: ox.distance.nearest_nodes(G, X=lon, Y=lat)
                      for name, (lat, lon) in shelter_points.items()}
    shelter_node_list = list(shelter_nodes.values())

    RISK_THRESHOLD = 0.8
    G_flooded = G.copy()
    edges_to_remove = [(u, v, k) for u, v, k, d in G_flooded.edges(keys=True, data=True)
                        if d['flood_risk'] > RISK_THRESHOLD]
    G_flooded.remove_edges_from(edges_to_remove)

    isolated_nodes = [n for n in G_flooded.nodes
                       if not any(nx.has_path(G_flooded, n, s) for s in shelter_node_list)]

    output = {
        "place_name": place_name,
        "note": "DUMMY flood_risk scores (random, seed=42) — pending real model.",
        "route_comparison": {
            "fastest_route": {"distance_km": round(f_dist/1000, 2),
                               "travel_time_min": round(f_time/60, 1),
                               "risk_weighted_time_min": round(f_risk/60, 1)},
            "safest_route": {"distance_km": round(s_dist/1000, 2),
                              "travel_time_min": round(s_time/60, 1),
                              "risk_weighted_time_min": round(s_risk/60, 1)}
        },
        "isolated_villages": {
            "total_nodes": len(G_flooded.nodes),
            "isolated_count": len(isolated_nodes),
            "isolated_percentage": round(100 * len(isolated_nodes) / len(G_flooded.nodes), 1)
        }
    }

    out_path = f"{place_tag}_routing_output.json"
    with open(out_path, "w") as f:
        json.dump(output, f, indent=2)

    print(f"DONE. Saved {out_path}")
    print(f"Isolated villages: {output['isolated_villages']['isolated_count']} "
          f"({output['isolated_villages']['isolated_percentage']}%)")

    return output


if __name__ == "__main__":
    # ---------------------------------------------------
    # List of districts to process — add more here anytime
    # using the same (place_name, place_tag, shelter_points) pattern
    # ---------------------------------------------------

    districts = [
        ("Uttarkashi District, Uttarakhand, India", "uttarkashi",
         {"Uttarkashi Town": (30.7333, 78.4399), "Barkot": (30.82, 78.20), "Dharasu": (30.6333, 78.3167)}),
        ("Chamoli District, Uttarakhand, India", "chamoli",
         {"Gopeshwar": (30.3833, 79.3167), "Joshimath": (30.5667, 79.5667)}),
        ("Lakhimpur District, Assam, India", "lakhimpur",
         {"North Lakhimpur": (27.2333, 94.1000)}),
        ("Pithoragarh District, Uttarakhand, India", "pithoragarh",
         {"Pithoragarh Town": (29.5833, 80.2167)}),
        ("Bageshwar District, Uttarakhand, India", "bageshwar",
         {"Bageshwar Town": (29.8333, 79.7667)}),
        ("Nainital District, Uttarakhand, India", "nainital",
         {"Nainital Town": (29.3919, 79.4542)}),
        ("Champawat District, Uttarakhand, India", "champawat",
         {"Champawat Town": (29.3350, 80.0900)}),
        ("Dhemaji District, Assam, India", "dhemaji",
         {"Dhemaji Town": (27.4833, 94.5667)}),
        ("Sonitpur District, Assam, India", "sonitpur",
         {"Tezpur": (26.6338, 92.8000)}),
        ("Biswanath District, Assam, India", "biswanath",
         {"Biswanath Chariali": (26.7333, 93.1500)}),
    ]

    successful = []
    failed = []

    for place_name, place_tag, shelter_points in districts:
        try:
            build_routing_for_place(place_name, place_tag, shelter_points)
            successful.append(place_tag)
        except Exception as e:
            print(f"\n⚠️ FAILED for {place_name}: {e}\n")
            failed.append(place_tag)

    print(f"\n{'='*50}")
    print(f"FINAL SUMMARY")
    print(f"{'='*50}")
    print(f"Successful ({len(successful)}): {successful}")
    print(f"Failed ({len(failed)}): {failed}")