<template>
  <div class="home">
    <img alt="Vue logo" src="../assets/logo.png">
    <CustomField></CustomField>
    <HelloWorld msg="Welcome to our fucking Vue.js App"/>
  </div>
</template>

<script>
// @ is an alias to /src
import HelloWorld from '@/components/HelloWorld.vue';
import CustomField from '../components/CustomField.vue';

export default {
  name: 'Home',
  components: {
    CustomField,
    HelloWorld,
  },
};
</script>
