const d3Force = require('d3-force');
const fs = require('fs');

const subgraph = {
  "nodes": [
    { "id": "1", "label": "cycle_node_1" },
    { "id": "2", "label": "cycle_node_2" },
    { "id": "3", "label": "cycle_node_3" },
    { "id": "4", "label": "cycle_node_4" }
  ],
  "edges": [
    { "source": "1", "target": "2" },
    { "source": "2", "target": "3" },
    { "source": "3", "target": "4" },
    { "source": "4", "target": "1" }
  ]
};

const width = 800;
const height = 550;
const centerX = width / 2;
const centerY = height / 2;

const nodes = subgraph.nodes.map(n => ({ ...n }));
const edges = subgraph.edges.map(e => ({ ...e }));

const sim = d3Force.forceSimulation(nodes)
  .force('link', d3Force.forceLink(edges).id(d => d.id).distance(110))
  .force('charge', d3Force.forceManyBody().strength(-350))
  .force('center', d3Force.forceCenter(centerX, centerY))
  .force('collision', d3Force.forceCollide().radius(35))
  .stop();

for (let i = 0; i < 300; ++i) sim.tick();

console.log(nodes.map(n => ({ id: n.id, x: n.x, y: n.y })));
