import Vue from 'vue';
import App from './App.vue';
import VueRouter from 'vue-router';
import updatePageTags from './utils/updatePageTags';
import routes from './routes';
import { init } from '../../../frontend/src/zar';
// To test from built dist bundle:
// import { init } from '../../../frontend/dist/zar.umd.js';

Vue.config.productionTip = false;
Vue.use(VueRouter);

const router = new VueRouter({
  mode: 'history', routes
});

const analytics = init({
  app: 'my-vue-app',
  gtmConfig: {
    containerId: process.env.VUE_APP_GTM_CONTAINER_ID
  },
  ga4Config: {
    trackingId: process.env.VUE_APP_GA4_TRACKING_ID,
    customDimensions: [
      {
        'name': 'vid',
        'callback': function (instance, config) { return instance.plugins.zar.getVID() }
      }
    ]
  },
  apiUrl: 'http://localhost/api/v1'
});

analytics.on('ready', () => {
  console.log('hasAdBlock', analytics.plugins.zar.hasAdBlock());
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

