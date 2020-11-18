const path = require('path');
const { CleanWebpackPlugin } = require('clean-webpack-plugin');

module.exports = {
  entry: './src/zar.js',
  module: {
    rules: [
      {
        test: /\.(js)$/,
        exclude: /node_modules/,
        use: ['babel-loader']
      }
    ]
  },
  optimization: {
    // minimize: false,
  },
  externals: {
    // 'analytics': 'analytics',
    // '@analytics/storage-utils': '@analytics/storage-utils',
    // '@analytics/google-analytics': '@analytics/google-analytics',
    // '@analytics/google-tag-manager': '@analytics/google-tag-manager',
    // 'axios': 'axios',
  },
  resolve: {
    extensions: ['*', '.js']
  },
  plugins: [
    new CleanWebpackPlugin(),
  ],
  output: {
    library: 'zar',
    libraryTarget: 'umd',
    filename: 'zar.bundle.js',
    path: path.resolve(__dirname, 'dist'),
  },
};