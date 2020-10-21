export default function zarPlugin(userConfig) {
  return {
    /* Name is a required field for plugins */
    name: 'my-plugin',

    /* Everything else below this is optional depending on your plugin requirements */
    config: {
      whatEver: userConfig.whatEver,
      elseYouNeed: userConfig.elseYouNeed
    },
    initialize: ({ config }) => {
      // load provider script to page
    },
    page: ({ payload }) => {
      // call provider specific page tracking
    },
    track: ({ payload }) => {
      // call provider specific event tracking
    },
    identify: ({ payload }) => {
      // call provider specific user identify method
    },
    loaded: () => {
      // return boolean so analytics knows when it can send data to third-party
      return !!window.myPluginLoaded
    },

    // /* Bootstrap runs when analytics starts */
    // bootstrap: ({ payload, config, instance }) => {
    //   // Do whatever on `bootstrap` event
    // },
    // pageStart: ({ payload, config, instance }) => {
    //   // Fire custom logic before analytics.page() calls
    // },
    // pageEnd: ({ payload, config, instance }) => {
    //   // Fire custom logic after analytics.page() calls
    // },
    // trackStart: ({ payload, config, instance }) => {
    //   // Fire custom logic before analytics.track() calls
    // },
    // 'track:customerio': ({ payload, config, instance }) => {
    //   // Fire custom logic before customer.io plugin runs.
    //   // Here you can customize the data sent to individual analytics providers
    // },
    // trackEnd: ({ payload, config, instance }) => {
    //   // Fire custom logic after analytics.track() calls
    // },
    // // ... hook into other events

    methods: {
      myCustomThing(one, two, three) {
        const analyticsInstance = this.instance
        console.log('Use full analytics instance', analyticsInstance)
      },
    }

  }
}