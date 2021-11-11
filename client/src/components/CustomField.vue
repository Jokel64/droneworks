<template>
  <div>
    <form class="form-group">
    <input :type="state" class="input-group">
    <button @click="action" class="btn-danger">Show</button>
    </form>
  </div>
</template>

<script>
export default {
  name: 'CustomField',
  data() {
    return {
      show: false,
    };
  },
  methods: {
    action() {
      this.show = !this.show;
    },
  },
  computed: {
    state() {
      if (this.show) {
        return 'text';
      }
      return 'password';
    },
  },
  created() {
    console.log('Test');
  },
};
</script>

<style scoped>

</style>
