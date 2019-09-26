import React from 'react'

import NoLocalNode from "./NoLocalNode";
import NodeInfo from "./NodeInfo";
import ProgressBar from "./shared_components/ProgressBar";

export default class Node extends React.Component {

  constructor(props) {
    super(props);
    this.state = {
      loaded: false
    };
  }

  componentDidMount() {
    this.initNodeInfoChecker();
  }

  componentWillUnmount() {
    this.destroyInfoChecker();
  }

  destroyInfoChecker() {
    clearInterval(this.state.nodeInfoTimer)
  }

  initNodeInfoChecker() {
    this.checkNodeInfo();
    this.setState({
      nodeInfoTimer: setInterval(() => {
        this.checkNodeInfo()
      }, 6000),
    });
  }

  // todo - move it to node class
  isNodeInstalled(nodeInfo) {
    return nodeInfo.data.status === 2
  }

  checkNodeInfo() {
    const url = '/node-info';
    let self = this;
    fetch(url)
      .then((resp) => resp.json())
      .then(function (data) {
        self.setState({
          nodeInstalled: self.isNodeInstalled(data),
          nodeInfo: data.data,
          loaded: true
        });

        if (data.errors && data.errors[0].code === 401) {
          self.props.history.push('/create-user');
        }

        if (!self.isNodeInstalled(data)) {
          self.props.history.push('/welcome');
        }

      })
      .catch(function (error) {
        console.log(error);
      });
  }

  render() {
    let content = this.state.nodeInstalled ? <NodeInfo darkMode={this.props.darkMode} node={this.state.nodeInfo}/> : <NoLocalNode/>;
    return (
      <div className="marg-30">
        {this.state.loaded ? content : <ProgressBar/>}
      </div>
    );
  }
}
