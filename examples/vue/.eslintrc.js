module.exports = {
    "env": {
        "node": true,
    },
    "extends": [
        "eslint:recommended",
        "plugin:vue/essential"
    ],
    "parserOptions": {
        "ecmaVersion": 10,
        "sourceType": "module"
    },
    "plugins": [
        "vue"
    ],
    "rules": {
        "no-console": 0,
        "no-unused-vars": 0,
        "no-debugger": 0,
        "semi": [2, "always"],
    }
};
