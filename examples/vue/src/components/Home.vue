<template>
  <div class="content">
    <h1>Using Analytics with Vue & vue-router</h1>
    <p>
      This is a
      <strong>zar</strong> example app based on an example from the
      <a href="https://github.com/davidwells/analytics">analytics module</a>
    </p>
    <p>Click the nav to route to pages & it will trigger page views. The console has additional debug output.</p>
    <p>
      <a href="https://getanalytics.io/">View the analytics docs</a>
    </p>
    <p>IDs: {{ ids }}</p>
    <button v-on:click="reset">Reset</button>
    <button v-on:click="reloadIds">Reload IDs</button>
    <button v-on:click="page">Trigger Page</button>
    <button v-on:click="track">Trigger Track</button>
    <button v-on:click="identify">Trigger Identify</button>
  </div>
</template>
<script>
export default {
  data: function () {
    return {
      ids: null
    }
  },
  methods: {
    reset: async function () {
      await this.$analytics.reset();
      this.ids = this.$analytics.plugins.zar.initIds();
    },
    reloadIds: function () {
      this.ids = this.$analytics.plugins.zar.getIds();
    },
    page: function () {
      this.$analytics.page();
    },
    track: function () {
      this.$analytics.track('event1', { attr1: 'val1', attr2: 'val2' })
    },
    identify: function () {
      this.$analytics.identify('user@example.com', { attr1: 'val1', attr2: 'val2' })
    }
  },
  created: function () {
    this.ids = this.$analytics.plugins.zar.getIds();
  }
}
</script>
