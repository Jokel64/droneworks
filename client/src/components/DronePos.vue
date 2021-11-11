<template>
  <div>
    <p>{{ msg }}</p>
    <form>
      <div class="form-group">
        <label for="x">X: </label>
        <input type="number" class="form-control" id="x" :value="x">
      </div>

      <div class="form-group">
        <label for="y">Y: </label>
        <input type="number" class="form-control" id="y" :value="y">
      </div>

      <div class="form-group">
        <label for="z">Z: </label>
        <input type="number" class="form-control" id="z" :value="z">
      </div>

      <button @click="sendMessage" class="btn btn-primary">Submit</button>
    </form>
  </div>
</template>

<script>
import axios from 'axios';

export default {
  name: 'DronePos',
  data() {
    return {
      msg: '',
      x: 0,
      y: 0,
      z: 0,
    };
  },
  methods: {
    getMessage() {
      const path = 'http://localhost:5000/';
      axios.get(path)
        .then((res) => {
          this.msg = res.data;
        })
        .catch((error) => {
          // eslint-disable-next-line
          console.error(error);
        });
    },
    sendMessage() {
      axios.post('http://localhost:5000/command/', { x: this.x, y: this.y, z: this.z })
        .then((response) => {
          console.log(response);
        })
        .catch((error) => {
          console.log(error);
        });
    },
  },
  created() {
    this.getMessage();
    setInterval(this.getMessage,
      500);
  },
};
</script>
