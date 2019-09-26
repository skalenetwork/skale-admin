

### React classes with skale-js library

Every react class that's using `skale` object should implement `connected` method:

```javascript
connected(skale) {
    this.setState({skale: skale, connected: true})
    // skale lib is ready to use now
  }
```

Adding new component to `App.js`:

1) Import component

```javascript
import LocalWallet from './LocalWallet';
```


2) Add ref to this component

In constructor:

```javascript
constructor(props) {
    ...
    this.localWalletComponent = React.createRef();
}
```

In switch:

```javascript
<Route exact path='/local-wallet/:address' render={(props) => <LocalWallet {...props} ref={this.localWalletComponent} />}/>
```

3) Invoke `connected` method in `updateWeb3Connector`:


```javascript
updateWeb3Connector(web3Connector) {
    this.setState({web3Connector: web3Connector});
    if (web3Connector && !this.state.libInit) {
      skale.initBothProviders(TEST_NODE_IP, TEST_NODE_PORT, web3Connector.provider);
      this.setState({libInit: true, skale: skale});
      this.localWalletComponent.current.connected(skale);
    }
}
```
