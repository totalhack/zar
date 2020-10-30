<template>
  <div class="content">
    <h1>Using Analytics with Vue & vue-router</h1>
    <p>
      This is a
      <strong>zar</strong> example app based on an example from the
      <a href="https://github.com/davidwells/analytics">analytics module</a>
    </p>
    <p>
      Click the nav to route to pages & it will trigger page views. The console
      has additional debug output.
    </p>
    <p>
      <a href="https://getanalytics.io/">View the analytics docs</a>
    </p>
    <pre>{{ JSON.stringify(storage, null, 2) }}</pre>
    <button v-on:click="reset">Reset</button>
    <button v-on:click="reload">Reload</button>
    <button v-on:click="clear">Clear</button>
    <button v-on:click="page">Trigger Page</button>
    <button v-on:click="track">Trigger Track</button>
    <button v-on:click="identify">Trigger Identify</button>
  </div>
</template>
<script>
export default {
  data: function () {
    return {
      storage: null
    };
  },
  methods: {
    reset: async function () {
      await this.$analytics.reset();
      this.$analytics.plugins.zar.initIds();
      this.storage = this.$analytics.plugins.zar.getStorage();
    },
    clear: async function () {
      await this.$analytics.reset();
      this.storage = this.$analytics.plugins.zar.getStorage();
    },
    reload: function () {
      this.storage = this.$analytics.plugins.zar.getStorage();
    },
    page: function () {
      this.$analytics.page();
    },
    track: function () {
      this.$analytics.track('event1', { attr1: 'val1', attr2: 'val2' });
    },
    identify: function () {
      this.$analytics.identify('user@example.com', { attr1: 'val1', attr2: 'val2' });
    }
  },
  created: function () {
    this.storage = this.$analytics.plugins.zar.getStorage();
  }
};
</script>
