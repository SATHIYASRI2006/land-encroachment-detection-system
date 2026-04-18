// Initialize map
const map = L.map('map').setView([13.0827, 80.2707], 12);

L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
  attribution: '&copy; OpenStreetMap contributors'
}).addTo(map);

// Plot locations
let markers = [];

fetch("http://127.0.0.1:5000/plots")
  .then(res => res.json())
  .then(data => {

    data.forEach(plot => {

      // DEBUG LOG
      console.log(plot.id, plot.lat, plot.lng);

      // FIX overlap issue
      const marker = L.circleMarker([
        plot.lat + (Math.random() * 0.002),
        plot.lng + (Math.random() * 0.002)
      ], {
        color:'blue',
        radius:8
      }).addTo(map);

      marker.on('click', ()=>{
        showPlot(plot.id);
        loadHistory(plot.id);
      });

      markers.push(marker);
    });

  })
  .catch(err => console.error("Error loading plots:", err));

// Show before/after
async function showPlot(plotId){
  const percentageEl = document.getElementById("percentage");
  const riskEl = document.getElementById("risk");
  const beforeImg = document.getElementById("beforeImage");
  const afterImg = document.getElementById("afterImage");

  percentageEl.innerText = "Loading...";
  riskEl.innerText = "-";

  try{
    const res = await fetch(`http://127.0.0.1:5000/analyze/${plotId}`);
    const data = await res.json();

    percentageEl.innerText = data.percentage + "%";
    riskEl.innerText = data.risk;

    beforeImg.src = `http://127.0.0.1:5000/static/data/${data.before_image}`;
    afterImg.src = `http://127.0.0.1:5000/static/data/${data.after_image}`;

    updateChart();

  }catch(err){
    console.error(err);
    percentageEl.innerText = "Error";
  }
}

// Load history timeline
async function loadHistory(plotId){
  const res = await fetch(`http://127.0.0.1:5000/history/${plotId}`);
  const data = await res.json();

  const container = document.getElementById("history");
  container.innerHTML = "";

  data.forEach(item=>{
    const box = document.createElement("div");

    const img = document.createElement("img");
    img.src = `http://127.0.0.1:5000/static/data/${item.image}`;

    const label = document.createElement("p");
    label.innerText = item.year;

    box.appendChild(img);
    box.appendChild(label);

    container.appendChild(box);
  });
}

// Chart
let myChart = null;

async function updateChart(){
  const res = await fetch("http://127.0.0.1:5000/stats");
  const data = await res.json();

  const ctx = document.getElementById("riskChart").getContext("2d");

  if(myChart) myChart.destroy();

  myChart = new Chart(ctx, {
    type:'bar',
    data:{
      labels:['High','Medium','Low'],
      datasets:[{
        label:'Plots',
        data:[data.High,data.Medium,data.Low],
        backgroundColor:['red','orange','green']
      }]
    },
    options:{
      responsive:true,
      maintainAspectRatio:false
    }
  });
}

// Load chart initially
document.addEventListener("DOMContentLoaded", updateChart);