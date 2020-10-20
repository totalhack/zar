module.exports = {
  chainWebpack: config => config.resolve.symlinks(false),
  // configureWebpack: (config) => {
  //   config.plugins = [
  //     new webpack.DefinePlugin({
  //       'process.env': config.dev.env,
  //     }),
  //   ]
  // }
}