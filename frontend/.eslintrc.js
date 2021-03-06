module.exports = {
    "env": {
        "browser": true,
        "es6": true
    },
    "extends": ["eslint:recommended", "plugin:compat/recommended"],
    "parserOptions": {
        "ecmaVersion": 8,
        "sourceType": "module"
    },
    "rules": {
        "no-console": 0,
        "no-unused-vars": 0,
        "no-debugger": 0,
        "semi": [2, "always"],
    },
    "settings": {
        "polyfills": ["Promise"]
    }
};
