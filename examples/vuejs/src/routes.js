import Home from './components/Home.vue';
import PageOne from './components/PageOne.vue';
import PageTwo from './components/PageTwo.vue';
import NumberPoolPage from './components/NumberPoolPage.vue';
import NumberPoolStats from './components/NumberPoolStats.vue';

const routes = [
  {
    path: '/',
    component: Home,
    meta: {
      title: 'Home Page',
    }
  },
  {
    path: '/one',
    component: PageOne,
    meta: {
      title: 'Page One',
    }
  },
  {
    path: '/two',
    component: PageTwo,
    meta: {
      title: 'Page Two',
    }
  },
  {
    path: '/number-pool-1',
    name: 'number-pool-1',
    component: NumberPoolPage,
    props: { poolId: 1 },
    meta: {
      title: 'Number Pool 1',
      reload: true,
    }
  },
  {
    path: '/number-pool-2',
    name: 'number-pool-2',
    component: NumberPoolPage,
    props: { poolId: 2 },
    meta: {
      title: 'Number Pool 2',
      reload: true,
    }
  },
  {
    path: '/number-pool-stats',
    name: 'number-pool-stats',
    component: NumberPoolStats,
    meta: {
      title: 'Number Pool Stats',
    }
  },
];

export default routes;
