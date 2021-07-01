<template>
  <div class="content">
    <h1>Number Pool</h1>
    <pre>{{ JSON.stringify(storage, null, 2) }}</pre>
    <button v-on:click="initPool">Init Pool</button>
    <button v-on:click="revertOverlay">Revert Overlay</button>
    <button v-on:click="removePoolSession">Remove Session</button>
    <br />
    <a href="tel:+18555660155" data-cta-attr="phone" class="button cta"
      ><span>855-566-0155</span></a
    >
    <br />
    <a href="tel:+18555660155" data-cta-attr="phone" class="button cta"
      ><span>Call 855-566-0155 link</span></a
    >
    <br />
    <span data-cta-attr="phone" class="button cta">855-566-0155</span>
    <br />
    <span data-cta-attr="phone" class="button cta">Call 855-566-0155 text</span>
  </div>
</template>
<script>
export default {
  props: {
    pl: Number,
    poolId: Number
  },
  data: function () {
    return {
      poolInterval: null,
      ctas: null
    };
  },
  computed: {
    storage: function () {
      return this.$analytics.plugins.zar.getStorage();
    },
  },
  methods: {
    getCTAs: function () {
      return document.querySelectorAll('.cta[data-cta-attr="phone"]');
    },
    initPool: function () {
      console.log("Initiliazing pool:", this.$props.poolId);
      this.$analytics.plugins.zar.initTrackingPool({
        poolId: this.$props.poolId,
        overlayElements: this.ctas,
        renew: false
      });
    },
    revertOverlay: function () {
      this.$analytics.plugins.zar.revertOverlayNumbers({ overlayElements: this.ctas });
    },
    removePoolSession: function () {
      this.$analytics.plugins.zar.removePoolSession({ overlayElements: this.ctas });
    }
  },
  mounted: async function () {
    this.ctas = this.getCTAs();
    console.log("Initiliazing pool:", this.$props.poolId);
    const resp = await this.$analytics.plugins.zar.initTrackingPool({
      poolId: this.$props.poolId,
      overlayElements: this.ctas,
      renew: true,
      renewalInterval: 10 * 1000
    });
    console.log(resp);
    this.poolInterval = resp.interval;
  },
  beforeDestroy() {
    this.revertOverlay();
    if (this.poolInterval) {
      console.log("Clearing interval", this.poolInterval);
      clearInterval(this.poolInterval);
    }
  },
};
</script>
