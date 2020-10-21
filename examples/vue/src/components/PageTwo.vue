<template>
  <div class="content">
    <h1>Page Two</h1>
    <p>IDs: {{ ids }}</p>
  </div>
</template>
<script>
export default {
  computed: {
    ids: function () {
      return this.$analytics.plugins.zar.getIds();
    }
  }
}
</script>
