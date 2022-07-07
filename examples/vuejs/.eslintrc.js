module.exports = {
    "env": {
        "node": true,
        "es6": true
    },
    "extends": [
        "eslint:recommended",
        "plugin:vue/essential"
    ],
    "parserOptions": {
        "ecmaVersion": 8,
        "sourceType": "module"
    },
    "plugins": [
        "vue"
    ],
    "rules": {
        "no-console": 0,
        "no-unused-vars": 0,
        "no-debugger": 0
    },
    "settings": {
        "polyfills": ["Promise"],
        "targets": null
    }
};
