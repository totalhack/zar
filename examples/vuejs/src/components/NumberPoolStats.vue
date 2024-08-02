<template>
  <div class="content">
    <h1>Number Pool</h1>
    <button v-on:click="refresh">Refresh</button>
    <pre>{{ JSON.stringify(stats, null, 2) }}</pre>
  </div>
</template>
<script>
export default {
  data: function () {
    return {
      stats: null
    };
  },
  methods: {
    refresh: async function () {
      this.stats = await this.$analytics.plugins.zar.getPoolStats({ with_contexts: true });
    }
  },
  mounted: function () {
    this.refresh();
  }
};
</script>
