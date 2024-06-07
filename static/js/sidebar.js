document.getElementById('open-sidebar').addEventListener('click', toggleSidebar);

let map;
window.initMap = () => {
  const directionsService = new google.maps.DirectionsService();
  const directionsRenderer = new google.maps.DirectionsRenderer();

  map = new google.maps.Map(document.getElementById("map"), {
    zoom: 7,
    center: { lat: 41.85, lng: -87.65 }
  });

  directionsRenderer.setMap(map);

  calculateAndDisplayRoute(directionsService, directionsRenderer);
};

function calculateAndDisplayRoute(directionsService, directionsRenderer) {
  fetch('/calculate')
    .then(response => response.json())
    .then(data => {
      
      directionsService.route({
        origin: data.start,
        destination: data.end,
        travelMode: "BICYCLING",
      }, 
      (response, status) => {
        if (status === "OK") {
          directionsRenderer.setDirections(response);
          loadRouteInfo(data.start, data.end);
        } 
        else {
          window.alert("Directions request failed due to " + status);
        }
      });
    });
}

function loadRouteInfo(start, end) {
  fetch(`/route_info?start=${start}&end=${end}`)
    .then(response => response.json())
    .then(data => {
      
      let routeInfo = document.getElementById('route-info');

      routeInfo.innerHTML += createCard('iconify-data-icon="ic:round-place"', 'Start Point', data.start);
      routeInfo.innerHTML += createCard('iconify-data-icon="ic:round-place"', 'End Point', data.end);
      routeInfo.innerHTML += createCard('iconify-data-icon="ic:round-place"', 'Avg Elevation', `${data.elevation} m`);
      routeInfo.innerHTML += createCard('iconify-data-icon="ic:round-place"', 'Calories Burned', `${data.calories_burned} kcal`);
      routeInfo.innerHTML += createCard('', 'AI Generated Response', data.response);

      openSidebar();
    });
}

function openSidebar() {
  document.getElementById("route-info").style.width = "350px";
  document.getElementById("open-sidebar").style.display = "none";
}

function closeSidebar() {
  document.getElementById("route-info").style.width = "0";
  document.getElementById("open-sidebar").style.display = "block";
}

function createCard(icon, category, heading) {
  return `
    <a class="card" href="#">
      <div class="card__background"></div>
      <div class="card__content">
        <p class="card__category">${icon} ${category}</p>
        <h3 class="card__heading">${heading}</h3>
      </div>
    </a>
  `;
}