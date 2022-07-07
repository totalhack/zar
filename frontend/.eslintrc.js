// eslint-disable-next-line no-undef
module.exports = {
    "env": {
        "browser": true,
        "es6": true
    },
    "extends": ["eslint:recommended"],
    "parserOptions": {
        "ecmaVersion": 8,
        "sourceType": "module"
    },
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
