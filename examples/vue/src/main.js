import Vue from 'vue';
import App from './App.vue';
import VueRouter from 'vue-router';
import updatePageTags from './utils/updatePageTags';
import routes from './routes';
// import { init } from '../../../frontend/src/zar';
import { init } from '../../../frontend/dist/zar.bundle.js';

Vue.config.productionTip = false;
Vue.use(VueRouter);

const router = new VueRouter({
  mode: 'history', routes
});

const analytics = init({
  app: 'my-vue-app',
  gtmContainerId: process.env.VUE_APP_GTM_CONTAINER_ID,
  apiUrl: 'http://localhost/api/v1',
  debug: true,
});

Vue.prototype.$analytics = analytics;

router.beforeEach(updatePageTags);

router.afterEach((to, from) => {
  console.log(`Route change to ${to.path} from ${from.path}`);
  analytics.page();
});

new Vue({
  router,
  render: h => h(App)
}).$mount('#app');

