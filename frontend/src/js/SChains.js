import React from 'react'
import {Collapse} from 'reactstrap';
import {LinearProgress} from 'rmwc/LinearProgress';
import {Icon} from 'rmwc/Icon';

import {FlexCol, FlexCont} from "./shared_components/Flex";
import ContainerIcon from "./shared_components/ContainerIcon";
import SChain from "./SChain";
import Button from "./SkaleButton/SkaleButton";

export default class Containers extends React.Component {

  constructor(props) {
    super(props);
    this.state = {
      loaded: false,
      containers: []
    };
  }

  componentDidMount() {
    this.initSChainsChecker();
  }

  componentWillUnmount() {
    this.destroySChainsChecker();
  }

  destroySChainsChecker() {
    clearInterval(this.state.sChainsInfoTimer)
  }

  initSChainsChecker() {
    this.checkSChainsInfo();
    this.setState({
      sChainsInfoTimer: setInterval(() => {
        this.checkSChainsInfo()
      }, 6000),
    });
  }

  checkSChainsInfo() {
      const url = '/schains-info';
      let self = this;
      fetch(url)
          .then((resp) => resp.json())
          .then(function (data) {
              self.setState({
                  containers: data.data['containers_stats'],
                  schains_configs: data.data['schains_configs'],
                  loaded: true
              });
          })
          .catch(function (error) {
              console.log(error);
          });
  }



  render() {

    const containers = this.state.containers.map((container, i) =>
      <div key={i}>
        <SChain darkMode={this.props.darkMode} dockerInfo={container}/>
        {/*<Container container={container}/>*/}
      </div>
    );

    let content = (
      <div style={{marginTop: '-10px', marginBottom: '-10px'}}>
        {(containers.length > 0) ? containers : <p className='padd-top-md text-center g-4'>No containers</p>}
      </div>
    );

    return (
      <div className="">
        {this.state.loaded ? content : <LinearProgress determinate={false}></LinearProgress>}







      </div>
    );
  }
}
