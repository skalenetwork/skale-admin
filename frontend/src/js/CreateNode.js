import React from 'react'
import {withRouter} from 'react-router-dom';

import {Input, Container, Tooltip} from 'reactstrap';
//import {Button} from 'rmwc/Button';
import Button from './SkaleButton/SkaleButton';

import PageTitle from "./shared_components/PageTitle";
import CardTitle from "./shared_components/CardTitle";
import SkInput from "./shared_components/SkInput";
import {Icon} from "rmwc/Icon";

const isValidIp = value => (/^(?:(?:^|\.)(?:2(?:5[0-5]|[0-4]\d)|1?\d?\d)){4}$/.test(value));
const isValidPort = value => (value > 0 && value < 65535);

class CreateNode extends React.Component {

  constructor(props) {
    super(props);

    this.state = {
      skaleNodeName: '',
      nodeIp: '',
      nodePublicIP: '',
      nodePort: ''
    };
    this.createNode = this.createNode.bind(this);

    this.checkName = this.checkName.bind(this);
    this.checkIp = this.checkIp.bind(this);
    this.checkPublicIP = this.checkPublicIP.bind(this);
    this.checkPort = this.checkPort.bind(this);

    this.setNodeName = this.setNodeName.bind(this);
    this.setNodeIp = this.setNodeIp.bind(this);
    this.setNodePublicIP = this.setNodePublicIP.bind(this);
    this.setNodePort = this.setNodePort.bind(this);
  }

  createNode() {

    if (!this.state.validNodeName || !this.state.validNodePort || !this.state.validNodeIp || !this.state.validNodePublicIP) {
      return
    }

    let nodeConfig = {
      ip: this.state.nodeIp,
      publicIP: this.state.nodePublicIP,
      port: this.state.nodePort,
      name: this.state.skaleNodeName
    };

    this.props.history.push('/installing-node');
    fetch('/create-node', {
      method: 'POST',
      headers: {
        'Accept': 'application/json',
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(nodeConfig)
    }).then(function (response) {
      return response.text()
    }, function (error) {
      console.error(error.message);
    })
  }

  async checkName(skaleNodeName) {
    if (skaleNodeName === '') {
      this.setState({validatingName: false, validNodeName: false, nodeNameError: 'Node name couldn\'t be empty'});
      return
    }
    this.setState({validatingName: true});
    let response = await fetch(`/check-node-name?nodeName=${skaleNodeName}`);
    let valid = await response.json();
    let nodeNameError = valid ? undefined : 'Name is already taken';
    this.setState({validatingName: false, validNodeName: valid, nodeNameError: nodeNameError});
  }

  setNodeName(value) {
    this.setState({skaleNodeName: value});
  }

  async checkIp(nodeIp) {
    if (nodeIp === '') {
      this.setState({validatingIp: false, validNodeIp: false, nodeIpError: 'Node IP couldn\'t be empty'});
      return
    }
    if (!isValidIp(nodeIp)) {
      this.setState({validatingIp: false, validNodeIp: false, nodeIpError: 'Not valid IP address'});
      return
    }

    this.setState({validatingIp: true});
    let response = await fetch(`/check-node-ip?nodeIp=${nodeIp}`);
    let valid = await response.json();
    let nodeIpError = valid ? undefined : 'IP address is already taken';
    this.setState({validatingIp: false, validNodeIp: valid, nodeIpError: nodeIpError});
  }

  setNodeIp(value) {
    this.setState({nodeIp: value});
  }


  async checkPort(nodePort) {
    let nodePortError;
    let validNodePort = true;
    if (nodePort === '') {
      nodePortError = 'Node port couldn\'t be empty';
      validNodePort = false;
    }
    if (!isValidPort(nodePort)) {
      nodePortError = 'Not valid port (should be in range 0-65535)';
      validNodePort = false;
    }
    this.setState({
      validatingPort: false,
      validNodePort: validNodePort,
      nodePortError: nodePortError
    });
  }

  setNodePort(value) {
    this.setState({nodePort: value});
  }


  async checkPublicIP(nodePublicIP) {
    let nodePublicIpError;
    let validNodePublicIP = true;
    if (nodePublicIP === '') {
      nodePublicIpError = 'Node IP couldn\'t be empty';
      validNodePublicIP = false;
    }
    if (!isValidIp(nodePublicIP)) {
      nodePublicIpError = 'Not valid IP address';
      validNodePublicIP = false;
    }
    this.setState({
      validatingPublicIP: false,
      validNodePublicIP: validNodePublicIP,
      nodePublicIpError: nodePublicIpError
    });
  }

  setNodePublicIP(value) {
    this.setState({nodePublicIP: value});
  }

  render() {
    return (
      <Container>
        <div className="marg-30">
          <PageTitle
            title="Create node"
            nopadd={true}
          />
          <div className="new-card marg-bott-30 padd-30 marg-top-30">
            <CardTitle icon="settings" color="neon-green" text="Node configuration"/>

            <div className="card-content">
              <div className="form-wrap" style={{maxWidth: "850px"}}>

                <SkInput
                  title='Name'
                  placeholder='Enter node name'
                  error={this.state.nodeNameError}
                  disabled={this.state.validatingName}
                  onBlur={this.checkName}
                  valid={this.state.validNodeName}
                  updateVariable={this.setNodeName}
                  value={this.state.skaleNodeName}
                />

                <br/>

                <SkInput
                  title='P2P IP'
                  placeholder='Enter p2p IP address'
                  error={this.state.nodeIpError}
                  disabled={this.state.validatingIp}
                  onBlur={this.checkIp}
                  valid={this.state.validNodeIp}
                  updateVariable={this.setNodeIp}
                  value={this.state.nodeIp}
                />

                <br/>


                <SkInput
                  title='Public IP'
                  placeholder='Enter public node IP address'
                  error={this.state.nodePublicIpError}
                  disabled={this.state.validatingPublicIP}
                  onBlur={this.checkPublicIP}
                  valid={this.state.validNodePublicIP}
                  updateVariable={this.setNodePublicIP}
                  value={this.state.nodePublicIP}
                />

                <br/>

                <SkInput
                  title='Port'
                  placeholder='Enter node port'
                  error={this.state.nodePortError}
                  disabled={this.state.validatingPort}
                  onBlur={this.checkPort}
                  valid={this.state.validNodePort}
                  updateVariable={this.setNodePort}
                  value={this.state.nodePort}
                />


                <br/>
                <Button type="button" className="marg-top-10 marg-bott-10" size="md" onClick={this.createNode}
                        disabled={this.state.nodePortError || this.state.nodeNameError || this.state.nodeIpError || this.state.nodePublicIpError}>
                  Create node
                </Button>
              </div>
            </div>
          </div>
        </div>
      </Container>
    );
  }
}

export default withRouter(CreateNode);