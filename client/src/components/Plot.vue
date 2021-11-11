<template>
  <div id="gd"></div>
</template>

<script type="module">
const Plotly = require('plotly.js-dist');

Plotly.newPlot('gd', [{ y: [1, 2, 3] }]);
</script>

<style scoped>

</style>
