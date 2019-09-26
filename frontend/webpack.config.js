const HtmlWebPackPlugin = require("html-webpack-plugin");
const path = require('path');
const Dotenv = require('dotenv-webpack');


module.exports = {
    entry: [
        'regenerator-runtime/runtime',
        './src/js/index.js'
    ],
    output: {
        path: path.resolve(__dirname, '..', 'static'),
        filename: "bundle.js",
        publicPath: '/static/'
    },
    module: {
        rules: [
            {
                test: /\.js?$/,
                exclude: /node_modules/,
                use: {
                    loader: "babel-loader",

                }
            },
            {
                test: /\.html$/,
                use: [
                    {
                        loader: "html-loader",
                        options: {minimize: true}
                    }
                ]
            },
            {
                test: /\.css$/,
                use: ['style-loader', 'css-loader']
            },
            {
                test: /\.scss$/,
                use: [{
                    loader: "style-loader" // creates style nodes from JS strings
                }, {
                    loader: "css-loader" // translates CSS into CommonJS
                }, {
                    loader: "sass-loader" // compiles Sass to CSS
                }]
            },
            {
                test: /\.(jpg|png|svg)$/,
                loader: 'file-loader',
                exclude: /node_modules/
            },

        ]
    },
    plugins: [
        new HtmlWebPackPlugin({
            template: "../templates/index.html",
            filename: "./index.html"
        }),
        new Dotenv()
    ],
    devServer: {
        contentBase: path.join(__dirname, '..', 'static'),
        filename: 'bundle.js',
        historyApiFallback: true,
        proxy: {
            "/": "http://localhost:3007"
        },
        port: '3333',

    }
};

