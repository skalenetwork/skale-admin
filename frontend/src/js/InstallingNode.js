import React from 'react'
import {withRouter} from 'react-router-dom';

import {Container, Row, Col} from 'reactstrap';
import {LinearProgress} from 'rmwc/LinearProgress';


class InstallingNode extends React.Component {

  componentDidMount() {
    this.initNodeInfoChecker();
  }

  initNodeInfoChecker() {
    this.checkNodeInfo();
    this.setState({
      nodeInfoTimer: setInterval(() => {
        this.checkNodeInfo()
      }, 6000),
    });
  }

  componentWillUnmount() {
    this.destroyInfoChecker();
  }

  destroyInfoChecker() {
    clearInterval(this.state.nodeInfoTimer)
  }

  // todo - move it to node class
  isNodeInstalled(nodeInfo) {
    return nodeInfo.status === 2
  }

  checkNodeInfo() {
    const url = '/node-info';
    let self = this;
    fetch(url)
      .then((resp) => resp.json())
      .then(function (data) {
        if (self.isNodeInstalled(data.data)) {
          self.props.history.push('/node');
          return
        }
        self.setState({
          nodeInfo: data,
          loaded: true
        })
      })
      .catch(function (error) {
        console.log(error);
      });
  }

  render() {
    return (
      <div className="marg-30 content-center text-center fl-center-vert">
        <Container>
          <Row>
            <Col md={{size: 6, offset: 3}}>
              <h3 className="g-6">
                Installing node
              </h3>
              <h6 className="padd-top-sm padd-bott-md g-4 fw-4">
                You can wait for the node to be created or explore other menu options and come back later
              </h6>
              <LinearProgress determinate={false}></LinearProgress>
            </Col>
          </Row>
        </Container>
      </div>
    )
  }
}

export default withRouter(InstallingNode);