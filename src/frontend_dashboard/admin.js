document.addEventListener("DOMContentLoaded", () => {
  const loginForm = document.getElementById("admin-login-form");
  if (loginForm) {
    loginForm.addEventListener("submit", async (e) => {
      e.preventDefault();
      const user = document.getElementById("username").value;
      const pass = document.getElementById("password").value;
      const errorMsg = document.getElementById("login-error");
      errorMsg.style.display = "none";

      try {
        const res = await fetch("/api/admin/login", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ username: user, password: pass })
        });
        const data = await res.json();

        if (data.status === "success") {
          localStorage.setItem("admin_token", data.token);
          window.location.href = "/static/admin-dashboard.html";
        } else {
          errorMsg.textContent = data.message || "Invalid credentials.";
          errorMsg.style.display = "block";
        }
      } catch (err) {
        errorMsg.textContent = "Server error. Please try again.";
        errorMsg.style.display = "block";
      }
    });
  }

  // Dashboard Logic
  const logoutBtn = document.getElementById("btn-logout");
  if (logoutBtn) {
    // Basic Auth Check
    const token = localStorage.getItem("admin_token");
    if (!token) {
      window.location.href = "/static/admin-login.html";
    }

    logoutBtn.addEventListener("click", () => {
      localStorage.removeItem("admin_token");
      window.location.href = "/static/admin-login.html";
    });

    // Map Logic for Admin Dashboard
    const mapSelect = document.getElementById("map-state-select");
    let adminMap = null;
    let layers = { routes: [], shelters: [] };

    const STATE_COORDS = { "Assam": [26.19, 92.76], "Uttarakhand": [30.0668, 79.0193] };

    function drawAdminMap(state) {
      const coords = STATE_COORDS[state];
      if (!adminMap) {
        adminMap = L.map("admin-map").setView(coords, 8);
        L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
          attribution: "&copy; OpenStreetMap contributors"
        }).addTo(adminMap);
      } else {
        adminMap.setView(coords, 8);
      }

      // Clear old layers
      layers.routes.forEach(l => adminMap.removeLayer(l));
      layers.shelters.forEach(l => adminMap.removeLayer(l));
      layers = { routes: [], shelters: [] };

      const [lat, lng] = coords;
      
      // Draw Flood Risk Zones (Red/Orange Heat Circles)
      const zones = [
        { center: [lat - 0.1, lng - 0.2], radius: 12000, color: "#ff5a5f", label: "Critical Risk (Red Alert)" },
        { center: [lat + 0.15, lng + 0.1], radius: 15000, color: "#ff9a3d", label: "High Risk (Orange Alert)" }
      ];
      zones.forEach((z) => {
        const c = L.circle(z.center, { color: z.color, fillColor: z.color, fillOpacity: 0.3, weight: 2, radius: z.radius }).addTo(adminMap);
        c.bindPopup(`<strong>${z.label}</strong><br/>Severe flood impact area.`);
        layers.routes.push(c); // using routes array just to keep it clearable
      });

      // Draw Blocked Route (Red)
      const blockedRoute = L.polyline([[lat - 0.1, lng - 0.2], [lat + 0.15, lng + 0.1]], { color: "#ff5a5f", weight: 4, dashArray: "5 5" }).addTo(adminMap);
      blockedRoute.bindPopup("<strong>⛔ Blocked Route</strong><br/>High flood risk. Do not use.");
      layers.routes.push(blockedRoute);

      // Draw Open Route (Green)
      const openRoute = L.polyline([[lat - 0.3, lng - 0.5], [lat + 0.4, lng + 0.6]], { color: "#31d17c", weight: 5 }).addTo(adminMap);
      openRoute.bindPopup("<strong>✅ Open Safe Route</strong><br/>Low flood exposure path. Safe for evacuation.");
      layers.routes.push(openRoute);

      // Draw shelters (simulated)
      const shelterIcon = L.divIcon({
        html: `<div style="background:#3ba7ff;color:#fff;width:28px;height:28px;border-radius:50%;display:flex;align-items:center;justify-content:center;font-size:14px;box-shadow:0 2px 6px rgba(0,0,0,.3)"><i class="fa fa-house-medical"></i></div>`,
        iconSize: [28, 28], iconAnchor: [14, 14]
      });
      [{ pos: [lat + 0.1, lng - 0.15], label: "Relief Shelter 1" }, { pos: [lat - 0.2, lng + 0.21], label: "Relief Shelter 2" }]
        .forEach((s) => {
          const m = L.marker(s.pos, { icon: shelterIcon }).addTo(adminMap);
          m.bindPopup(`<strong>${s.label}</strong><br/>Verified safe shelter`);
          layers.shelters.push(m);
        });
    }

    drawAdminMap(mapSelect.value);
    mapSelect.addEventListener("change", (e) => drawAdminMap(e.target.value));

    // Broadcast Logic
    const broadcastForm = document.getElementById("broadcast-form");
    const toast = document.getElementById("bc-toast");
    
    broadcastForm.addEventListener("submit", async (e) => {
      e.preventDefault();
      const area = document.getElementById("bc-area").value;
      const severity = document.getElementById("bc-severity").value;
      const message = document.getElementById("bc-message").value;

      try {
        const res = await fetch("/api/admin/broadcast", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ token: localStorage.getItem("admin_token"), targetArea: area, severity, message })
        });
        const data = await res.json();
        
        if(data.status === "success") {
          toast.style.display = "block";
          document.getElementById("bc-message").value = "";
          setTimeout(() => { toast.style.display = "none"; }, 4000);
        } else {
          alert("Error: " + data.message);
        }
      } catch (err) {
        alert("Failed to send broadcast. Check connection.");
      }
    });
  }
});
