import Vue from 'vue';
import VueRouter from 'vue-router';
import Home from '../views/Home.vue';
import Ping from '../components/Ping.vue';
import DronePos from '../components/DronePos.vue';
import Plot from '../components/Plot.vue';

Vue.use(VueRouter);

const routes = [
  {
    path: '/',
    name: 'Home',
    component: Home,
  },
  {
    path: '/about',
    name: 'About',
    // route level code-splitting
    // this generates a separate chunk (about.[hash].js) for this route
    // which is lazy-loaded when the route is visited.
    component: () => import(/* webpackChunkName: "about" */ '../views/About.vue'),
  },
  {
    path: '/ping',
    name: 'Ping',
    component: Ping,
  },
  {
    path: '/drone_pos',
    name: 'DronePos',
    component: DronePos,
  },
  {
    path: '/plot',
    name: 'Plot',
    component: Plot,
  },
];

const router = new VueRouter({
  mode: 'history',
  base: process.env.BASE_URL,
  routes,
});

export default router;
